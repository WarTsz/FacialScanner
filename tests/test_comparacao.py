"""Comparação de imagens com o catálogo (8.2): uma ou mais imagens de um objeto -> top 10."""

import hashlib

import cv2
import numpy as np
import pytest

from scanner.captura import ProcessadorFrames
from scanner.catalogo import PADRAO_NOME_SCAN, Catalogo
from scanner.config import carregar_config
from scanner.embedding import normalizar
from scanner.motor import Motor
from scanner.ranking import Decisao, Indice
from tests.conftest import RAIZ, ler, requer_modelos
from tests.seed_exemplo import sequencia_camera

pytestmark = requer_modelos


@pytest.fixture(scope="module")
def processador():
    return ProcessadorFrames.criar(carregar_config(RAIZ / "config.toml"))


@pytest.fixture
def motor(tmp_path, processador):
    cfg = carregar_config(RAIZ / "config.toml")
    cfg.catalogo.diretorio_dados = tmp_path / "data"
    cat = Catalogo(cfg.catalogo.diretorio_dados)
    m = Motor(cfg, processador, cat, Indice.carregar(cat))
    yield m
    m.fechar()


def _fotos(pasta, prefixo, img, n, semente):
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for i, f in enumerate(sequencia_camera(img, n, semente=semente)):
        c = pasta / f"{prefixo}{i + 1}.png"
        cv2.imwrite(str(c), f)
        caminhos.append(c)
    return caminhos


def _catalogo_com(motor, tmp_path, *objetos):
    """Cria um item por objeto (via adição manual) e devolve os itens."""
    itens = []
    for n, (nome, arquivo) in enumerate(objetos):
        r = motor.adicionar_imagens(_fotos(tmp_path / f"cat-{nome}", nome, ler(arquivo), 2, semente=50 + n))
        itens.append(r.item)
    return itens


def _foto_dados(diretorio) -> tuple:
    arquivos = sorted(
        (str(p.relative_to(diretorio)), p.stat().st_size)
        for p in diretorio.rglob("*")
        if p.is_file() and p.suffix != ".db" and "journal" not in p.name
    )
    cat = Catalogo(diretorio)
    conteudo = hashlib.sha256(
        repr(cat._con.execute("SELECT * FROM itens").fetchall()).encode()
        + repr(cat._con.execute("SELECT * FROM imagens").fetchall()).encode()
    ).hexdigest()
    cat.fechar()
    return arquivos, conteudo


def test_uma_imagem_mostra_o_top_do_catalogo(motor, tmp_path):
    gata, foguete = _catalogo_com(motor, tmp_path, ("gata", "chelsea.png"), ("foguete", "rocket.jpg"))
    a = _fotos(tmp_path / "q", "gata", ler("chelsea.png"), 1, semente=1)
    r = motor.buscar_por_imagens(a)
    assert r.valido and r.usadas == ["gata1.png"]
    assert [x.item_id for x in r.resultados][:2] == [gata.id, foguete.id]
    assert r.resultados[0].porcentagem >= 90
    assert r.decisao == Decisao.DESCARTAR and r.item is None


def test_varias_imagens_usam_a_media_do_grupo(motor, tmp_path):
    _catalogo_com(motor, tmp_path, ("foguete", "rocket.jpg"))
    q = _fotos(tmp_path / "q", "caneca", ler("coffee.png"), 4, semente=1)
    r = motor.buscar_por_imagens(q)
    assert r.usadas == ["caneca1.png", "caneca2.png", "caneca3.png", "caneca4.png"]
    assert r.fora_do_grupo == [] and r.descartadas_qualidade == []
    vs = np.stack([motor.processador.processar(cv2.imread(str(c)), fracao_moldura=1.0).vetor for c in q])
    esperado = float(normalizar(vs.mean(axis=0)) @ motor.indice._matriz[0])
    foguete = next(x for x in r.resultados if x.item_id == 1)
    assert foguete.cosseno == pytest.approx(
        max(esperado, float(normalizar(vs.mean(axis=0)) @ motor.indice._matriz[1])), abs=1e-5
    )


def test_imagem_borrada_e_descartada_com_motivo(motor, tmp_path):
    q = _fotos(tmp_path / "q", "caneca", ler("coffee.png"), 2, semente=1)
    borrada = tmp_path / "q" / "borrada.png"
    cv2.imwrite(str(borrada), cv2.GaussianBlur(ler("coffee.png"), (31, 31), 0))
    texto = tmp_path / "q" / "notas.png"
    texto.write_text("não é imagem")
    r = motor.buscar_por_imagens([q[0], borrada, q[1], texto])
    assert r.usadas == ["caneca1.png", "caneca2.png"]
    assert r.descartadas_qualidade == [("borrada.png", "borrado"), ("notas.png", "não é uma imagem legível")]


def test_imagem_diferente_fica_fora_do_grupo(motor, tmp_path):
    canecas = _fotos(tmp_path / "q", "caneca", ler("coffee.png"), 3, semente=1)
    foguete = _fotos(tmp_path / "q", "foguete", ler("rocket.jpg"), 1, semente=2)
    r = motor.buscar_por_imagens([canecas[0], foguete[0], canecas[1], canecas[2]])
    assert r.usadas == ["caneca1.png", "caneca2.png", "caneca3.png"]
    assert r.fora_do_grupo == ["foguete1.png"]


def test_empate_usa_o_primeiro_grupo(motor, tmp_path):
    canecas = _fotos(tmp_path / "q", "caneca", ler("coffee.png"), 2, semente=1)
    foguetes = _fotos(tmp_path / "q", "foguete", ler("rocket.jpg"), 2, semente=2)
    r = motor.buscar_por_imagens([foguetes[0], canecas[0], canecas[1], foguetes[1]])
    assert r.usadas == ["foguete1.png", "foguete2.png"]
    assert r.fora_do_grupo == ["caneca1.png", "caneca2.png"]


def test_nenhuma_imagem_valida_nao_busca_nem_grava(motor, tmp_path):
    _catalogo_com(motor, tmp_path, ("gata", "chelsea.png"))
    antes = _foto_dados(motor.cfg.catalogo.diretorio_dados)
    escura = tmp_path / "q" / "escura.png"
    escura.parent.mkdir()
    cv2.imwrite(str(escura), (ler("rocket.jpg") * 0.05).astype(np.uint8))
    r = motor.buscar_por_imagens([escura])
    assert not r.valido and r.decisao is None and r.resultados == [] and r.item is None
    assert r.descartadas_qualidade == [("escura.png", "escuro demais")]
    assert _foto_dados(motor.cfg.catalogo.diretorio_dados) == antes


def test_objeto_novo_vira_item_com_todas_as_imagens_do_grupo(motor, tmp_path):
    _catalogo_com(motor, tmp_path, ("gata", "chelsea.png"))
    canecas = _fotos(tmp_path / "q", "caneca", ler("coffee.png"), 3, semente=1)
    foguete = _fotos(tmp_path / "q", "foguete", ler("rocket.jpg"), 1, semente=2)
    r = motor.buscar_por_imagens([*canecas, *foguete])
    assert r.resultados[0].porcentagem < 90
    assert r.decisao == Decisao.INSERIR
    assert r.item is not None and PADRAO_NOME_SCAN.match(r.item.nome) and r.item.origem == "scan"
    assert len(r.item.imagens) == 3  # só o grupo escolhido
    assert motor.indice.contem_item(r.item.id)
    # O item novo não aparece no próprio ranking.
    assert all(x.item_id != r.item.id for x in r.resultados)


def test_objeto_ja_catalogado_nao_grava_nada(motor, tmp_path):
    _catalogo_com(motor, tmp_path, ("caneca", "coffee.png"), ("gata", "chelsea.png"))
    antes = _foto_dados(motor.cfg.catalogo.diretorio_dados)
    q = _fotos(tmp_path / "q", "caneca", ler("coffee.png"), 2, semente=7)
    r = motor.buscar_por_imagens(q)
    assert r.resultados[0].porcentagem >= 90
    assert r.decisao == Decisao.DESCARTAR and r.item is None
    assert _foto_dados(motor.cfg.catalogo.diretorio_dados) == antes


def test_rosto_vira_item_sem_consentimento(motor, tmp_path):
    _catalogo_com(motor, tmp_path, ("caneca", "coffee.png"))
    rostos = _fotos(tmp_path / "q", "rosto", ler("astronaut.png"), 2, semente=1)
    assert motor.processador.processar(cv2.imread(str(rostos[0])), fracao_moldura=1.0).tem_rosto
    r = motor.buscar_por_imagens(rostos)
    assert r.decisao == Decisao.INSERIR  # nunca PEDIR_CONSENTIMENTO
    assert r.item is not None and len(r.item.imagens) == 2
