"""Fachada que liga processamento, catálogo, índice e regra de inserção.

Usada pela interface gráfica. Todos os métodos podem rodar fora da thread da GUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from scanner.calibracao import Escala
from scanner.captura import FrameProcessado, ProcessadorFrames, Scan, agregar
from scanner.catalogo import Catalogo, Item, imagens_de_arquivos, imagens_do_scan
from scanner.comparacao import agrupar_por_semelhanca, escolher_grupo
from scanner.config import Config
from scanner.embedding import normalizar
from scanner.ranking import Decisao, Indice, Resultado, decidir_insercao


@dataclass
class ResultadoScan:
    scan: Scan
    resultados: list[Resultado]
    decisao: Decisao


@dataclass
class ResultadoAdicao:
    item: Item | None  # None quando nenhuma imagem era válida
    ignoradas: list[tuple[str, str]]  # (arquivo, motivo)

    @property
    def adicionadas(self) -> int:
        return len(self.item.imagens) if self.item else 0


@dataclass
class ResultadoBuscaImagens:
    """Busca no catálogo a partir de imagens de um mesmo objeto."""

    usadas: list[str]  # arquivos do grupo escolhido, na ordem
    descartadas_qualidade: list[tuple[str, str]]  # (arquivo, motivo)
    fora_do_grupo: list[str]  # válidas, mas diferentes do grupo escolhido
    resultados: list[Resultado]
    decisao: Decisao | None  # None quando nenhuma imagem era válida
    item: Item | None = None  # item criado quando a decisão é INSERIR

    @property
    def valido(self) -> bool:
        return bool(self.usadas)


class Motor:
    def __init__(self, cfg: Config, processador, catalogo: Catalogo, indice: Indice):
        self.cfg = cfg
        self.processador = processador
        self.catalogo = catalogo
        self.indice = indice
        self.escala = Escala(cfg.calibracao.cos_zero, cfg.calibracao.cos_noventa)

    @classmethod
    def criar(cls, cfg: Config) -> "Motor":
        catalogo = Catalogo(cfg.catalogo.diretorio_dados)
        return cls(cfg, ProcessadorFrames.criar(cfg), catalogo, Indice.carregar(catalogo))

    def processar_frame(self, img: np.ndarray) -> FrameProcessado:
        # Frame da câmera: o sujeito é o que está dentro da moldura da tela.
        return self.processador.processar(img, rosto_na_moldura=True)

    def concluir(self, frames: list[FrameProcessado]) -> ResultadoScan:
        """Agrega os frames, busca o ranking e decide a inserção. Lança FalhaScan."""
        scan = agregar(frames, self.cfg.captura.min_frames_validos)
        resultados = self.indice.buscar(scan.vetor, self.escala, self.cfg.ranking.top)
        decisao = decidir_insercao(resultados, scan.contem_rosto, self.cfg.ranking.limiar_insercao)
        return ResultadoScan(scan, resultados, decisao)

    def inserir(self, scan: Scan) -> Item:
        imagens = imagens_do_scan(scan, self.cfg.catalogo.imagens_por_item)
        item = self.catalogo.inserir_scan(imagens)
        self.indice.adicionar(item, np.stack([i.vetor for i in imagens]))
        scan.descartar()
        return item

    def adicionar_imagens(self, caminhos) -> ResultadoAdicao:
        """Adição manual: as imagens válidas viram um item guardado como um scan.

        Sem regra dos 90% e sem consentimento; todas as imagens válidas são guardadas.
        """
        novas, ignoradas = imagens_de_arquivos(self.processador, caminhos)
        if not novas:
            return ResultadoAdicao(None, ignoradas)
        item = self.catalogo.inserir_scan(novas)
        self.indice.adicionar(item, np.stack([i.vetor for i in novas]))
        return ResultadoAdicao(item, ignoradas)

    def buscar_por_imagens(self, caminhos) -> ResultadoBuscaImagens:
        """Top 10 do catálogo para uma ou mais imagens de um mesmo objeto.

        Descarta imagens ruins, agrupa as válidas por semelhança e usa o maior grupo
        (em empate, o primeiro formado). Abaixo de 90%, o grupo vira um item novo,
        sem pedido de consentimento. Com 90% ou mais, nada é gravado.
        """
        nomes: list[str] = []
        novas = []
        descartadas: list[tuple[str, str]] = []
        for caminho in caminhos:  # um por vez, para manter o nome de cada imagem válida
            validas, ignoradas = imagens_de_arquivos(self.processador, [caminho])
            descartadas.extend(ignoradas)
            for imagem in validas:
                nomes.append(Path(caminho).name)
                novas.append(imagem)
        if not novas:
            return ResultadoBuscaImagens([], descartadas, [], [], None)

        vetores = np.stack([np.asarray(n.vetor, np.float32) for n in novas])
        grupos = agrupar_por_semelhanca(
            vetores, self.escala, self.cfg.comparacao.similaridade_minima
        )
        escolhidos = grupos[escolher_grupo(grupos)]
        fora = [nomes[i] for i in range(len(novas)) if i not in escolhidos]

        vetor = normalizar(vetores[escolhidos].mean(axis=0))
        resultados = self.indice.buscar(vetor, self.escala, self.cfg.ranking.top)
        decisao = decidir_insercao(
            resultados, contem_rosto=False, limiar=self.cfg.ranking.limiar_insercao
        )
        item = None
        if decisao == Decisao.INSERIR:  # sem consentimento, por decisão do produto
            item = self.catalogo.inserir_scan([novas[i] for i in escolhidos])
            self.indice.adicionar(item, vetores[escolhidos])
        return ResultadoBuscaImagens(
            [nomes[i] for i in escolhidos], descartadas, fora, resultados, decisao, item
        )

    def descartar(self, scan: Scan) -> None:
        scan.descartar()

    def remover(self, item_id: int) -> Item:
        item = self.catalogo.remover(item_id)
        self.indice.remover(item_id)
        return item

    def itens_scan(self) -> list[Item]:
        return self.catalogo.listar("scan")

    def fechar(self) -> None:
        self.catalogo.fechar()
