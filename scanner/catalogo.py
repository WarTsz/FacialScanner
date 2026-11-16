"""Catálogo de itens: SQLite (itens, imagens, vetores) e arquivos de imagem."""

from __future__ import annotations

import re
import shutil
import sqlite3
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from scanner.embedding import DIMENSAO

PADRAO_NOME_SCAN = re.compile(r"^item-\d{6}$")

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS itens (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT    NOT NULL UNIQUE,
    origem    TEXT    NOT NULL CHECK (origem IN ('seed', 'scan')),
    criado_em TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS imagens (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id   INTEGER NOT NULL REFERENCES itens(id) ON DELETE CASCADE,
    caminho   TEXT    NOT NULL,
    qualidade REAL    NOT NULL,
    vetor     BLOB    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_imagens_item ON imagens(item_id);
"""


class ErroCatalogo(RuntimeError):
    pass


@dataclass(frozen=True)
class ImagemNova:
    recorte: np.ndarray
    vetor: np.ndarray
    qualidade: float


@dataclass(frozen=True)
class Imagem:
    id: int
    item_id: int
    caminho: Path
    qualidade: float


@dataclass(frozen=True)
class Item:
    id: int
    nome: str
    origem: str
    criado_em: str
    imagens: tuple[Imagem, ...]


@dataclass(frozen=True)
class Vetores:
    """Todos os vetores do catálogo, alinhados por linha."""

    imagem_ids: np.ndarray
    item_ids: np.ndarray
    matriz: np.ndarray  # (N, 384) float32
    caminhos: list[Path]


def nome_scan(item_id: int) -> str:
    return f"item-{item_id:06d}"


def imagens_do_scan(scan, k: int) -> list[ImagemNova]:
    """Os k frames de maior qualidade do scan, prontos para inserção."""
    return [
        ImagemNova(f.recorte, f.vetor, f.qualidade.pontuacao) for f in scan.melhores(k)
    ]


def imagens_de_arquivos(processador, caminhos) -> tuple[list[ImagemNova], list[tuple[str, str]]]:
    """Processa arquivos de imagem como no seed: qualidade e recorte com a imagem inteira.

    Retorna as imagens válidas, na ordem dos arquivos, e as ignoradas como (arquivo, motivo).
    """
    novas: list[ImagemNova] = []
    ignoradas: list[tuple[str, str]] = []
    for caminho in map(Path, caminhos):
        try:  # imdecode aceita caminhos com acentos em qualquer sistema
            img = cv2.imdecode(np.fromfile(str(caminho), np.uint8), cv2.IMREAD_COLOR)
        except (OSError, ValueError):
            img = None
        if img is None:
            ignoradas.append((caminho.name, "não é uma imagem legível"))
            continue
        fp = processador.processar(img, fracao_moldura=1.0)
        if not fp.valido:
            ignoradas.append((caminho.name, fp.motivo or "inválida"))
            continue
        novas.append(ImagemNova(fp.recorte, fp.vetor, fp.qualidade.pontuacao))
    return novas, ignoradas


class Catalogo:
    """Acesso ao catálogo. Seguro para uso a partir de várias threads."""

    def __init__(self, diretorio_dados: Path):
        self.diretorio = Path(diretorio_dados)
        self.dir_imagens = self.diretorio / "images"
        self.dir_imagens.mkdir(parents=True, exist_ok=True)
        self._trava = threading.RLock()
        self._con = sqlite3.connect(
            self.diretorio / "catalogo.db", check_same_thread=False, isolation_level=None
        )
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(_ESQUEMA)

    def fechar(self) -> None:
        with self._trava:
            self._con.close()

    # ----------------------------------------------------------------- leitura

    def _imagens_de(self, item_id: int) -> tuple[Imagem, ...]:
        linhas = self._con.execute(
            "SELECT id, item_id, caminho, qualidade FROM imagens WHERE item_id = ? ORDER BY id",
            (item_id,),
        ).fetchall()
        return tuple(Imagem(i, it, self.diretorio / c, q) for i, it, c, q in linhas)

    def obter(self, item_id: int) -> Item | None:
        with self._trava:
            linha = self._con.execute(
                "SELECT id, nome, origem, criado_em FROM itens WHERE id = ?", (item_id,)
            ).fetchone()
            return Item(*linha, self._imagens_de(linha[0])) if linha else None

    def listar(self, origem: str | None = None) -> list[Item]:
        with self._trava:
            sql = "SELECT id, nome, origem, criado_em FROM itens"
            args: tuple = ()
            if origem:
                sql += " WHERE origem = ?"
                args = (origem,)
            linhas = self._con.execute(sql + " ORDER BY id", args).fetchall()
            return [Item(*l, self._imagens_de(l[0])) for l in linhas]

    def existe_nome(self, nome: str) -> bool:
        with self._trava:
            return (
                self._con.execute("SELECT 1 FROM itens WHERE nome = ?", (nome,)).fetchone()
                is not None
            )

    def total_itens(self) -> int:
        with self._trava:
            return self._con.execute("SELECT COUNT(*) FROM itens").fetchone()[0]

    def vetores(self) -> Vetores:
        with self._trava:
            linhas = self._con.execute(
                "SELECT id, item_id, caminho, vetor FROM imagens ORDER BY id"
            ).fetchall()
        if not linhas:
            return Vetores(
                np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros((0, DIMENSAO), np.float32), []
            )
        return Vetores(
            np.array([l[0] for l in linhas], np.int64),
            np.array([l[1] for l in linhas], np.int64),
            np.stack([np.frombuffer(l[3], np.float32) for l in linhas]),
            [self.diretorio / l[2] for l in linhas],
        )

    # ----------------------------------------------------------------- escrita

    def _inserir(self, origem: str, nome: str | None, imagens: list[ImagemNova]) -> Item:
        if not imagens:
            raise ErroCatalogo("um item precisa de pelo menos uma imagem")
        agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._trava:
            pasta: Path | None = None
            cur = self._con.cursor()
            cur.execute("BEGIN")
            try:
                provisorio = nome or f"__novo__{threading.get_ident()}"
                cur.execute(
                    "INSERT INTO itens (nome, origem, criado_em) VALUES (?, ?, ?)",
                    (provisorio, origem, agora),
                )
                item_id = cur.lastrowid
                if nome is None:
                    nome = nome_scan(item_id)
                    cur.execute("UPDATE itens SET nome = ? WHERE id = ?", (nome, item_id))
                pasta = self.dir_imagens / nome
                pasta.mkdir(parents=True, exist_ok=False)
                for n, img in enumerate(imagens, start=1):
                    arquivo = pasta / f"{n}.jpg"
                    if not cv2.imwrite(str(arquivo), img.recorte, [cv2.IMWRITE_JPEG_QUALITY, 92]):
                        raise ErroCatalogo(f"falha ao gravar {arquivo}")
                    vetor = np.asarray(img.vetor, np.float32)
                    if vetor.shape != (DIMENSAO,):
                        raise ErroCatalogo(f"vetor com formato inválido: {vetor.shape}")
                    cur.execute(
                        "INSERT INTO imagens (item_id, caminho, qualidade, vetor) VALUES (?, ?, ?, ?)",
                        (
                            item_id,
                            str(arquivo.relative_to(self.diretorio)),
                            float(img.qualidade),
                            vetor.tobytes(),
                        ),
                    )
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                if pasta is not None and pasta.exists():
                    shutil.rmtree(pasta, ignore_errors=True)
                raise
            return self.obter(item_id)

    def inserir_scan(self, imagens: list[ImagemNova]) -> Item:
        """Novo item de origem "scan" com nome automático item-NNNNNN."""
        return self._inserir("scan", None, imagens)

    def inserir_seed(self, nome: str, imagens: list[ImagemNova]) -> Item:
        if PADRAO_NOME_SCAN.match(nome):
            raise ErroCatalogo(f"o nome '{nome}' é reservado para itens criados por scan")
        if self.existe_nome(nome):
            raise ErroCatalogo(f"já existe um item chamado '{nome}'")
        return self._inserir("seed", nome, imagens)

    def remover(self, item_id: int) -> Item:
        """Remove definitivamente um item de origem "scan" (linhas, vetores e arquivos)."""
        with self._trava:
            item = self.obter(item_id)
            if item is None:
                raise ErroCatalogo(f"item {item_id} não existe")
            if item.origem != "scan":
                raise ErroCatalogo("só itens criados por scan podem ser removidos")
            self._con.execute("DELETE FROM itens WHERE id = ?", (item_id,))
            shutil.rmtree(self.dir_imagens / item.nome, ignore_errors=True)
            return item


# --------------------------------------------------------------------------- seed


def importar_seed(catalogo: Catalogo, processador, pasta: Path, saida=sys.stdout) -> list[Item]:
    """Importa cada subpasta de `pasta` como um item de origem "seed".

    Cada imagem passa pelo mesmo filtro de qualidade e recorte do scan. Sem uma
    moldura na tela, o recorte de objeto usa o maior quadrado central da imagem.
    """
    from scanner.captura import EXTENSOES_IMAGEM

    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroCatalogo(f"pasta de seed não encontrada: {pasta}")
    criados: list[Item] = []
    for sub in sorted(p for p in pasta.iterdir() if p.is_dir()):
        nome = sub.name
        if PADRAO_NOME_SCAN.match(nome):
            print(f"[pulado] {nome}: nome reservado para itens criados por scan", file=saida)
            continue
        if catalogo.existe_nome(nome):
            print(f"[pulado] {nome}: já existe no catálogo", file=saida)
            continue
        novas: list[ImagemNova] = []
        arquivos = sorted(p for p in sub.iterdir() if p.suffix.lower() in EXTENSOES_IMAGEM)
        for arq in arquivos:
            img = cv2.imread(str(arq))
            if img is None:
                print(f"  [ignorada] {nome}/{arq.name}: não é uma imagem legível", file=saida)
                continue
            fp = processador.processar(img, fracao_moldura=1.0)
            if not fp.valido:
                print(f"  [ignorada] {nome}/{arq.name}: {fp.motivo}", file=saida)
                continue
            novas.append(ImagemNova(fp.recorte, fp.vetor, fp.qualidade.pontuacao))
        if not novas:
            print(f"[pulado] {nome}: nenhuma imagem válida ({len(arquivos)} arquivo(s))", file=saida)
            continue
        item = catalogo.inserir_seed(nome, novas)
        criados.append(item)
        print(f"[criado] {nome}: {len(novas)} de {len(arquivos)} imagem(ns)", file=saida)
    print(f"Seed concluído: {len(criados)} item(ns) criado(s).", file=saida)
    return criados


def comando_seed(caminho_config: Path | None, pasta: Path) -> int:
    from scanner.captura import ProcessadorFrames
    from scanner.config import carregar_config
    from scanner.modelos import ModelosAusentes

    cfg = carregar_config(caminho_config)
    try:
        processador = ProcessadorFrames.criar(cfg)
    except ModelosAusentes as exc:
        print(exc, file=sys.stderr)
        return 1
    catalogo = Catalogo(cfg.catalogo.diretorio_dados)
    try:
        importar_seed(catalogo, processador, pasta)
    except ErroCatalogo as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        catalogo.fechar()
    return 0
