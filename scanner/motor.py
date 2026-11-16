"""Fachada que liga processamento, catálogo, índice e regra de inserção.

Usada pela interface gráfica. Todos os métodos podem rodar fora da thread da GUI.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scanner.calibracao import Escala
from scanner.captura import FrameProcessado, ProcessadorFrames, Scan, agregar
from scanner.catalogo import Catalogo, Item, imagens_de_arquivos, imagens_do_scan
from scanner.config import Config
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
