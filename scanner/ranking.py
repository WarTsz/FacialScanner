"""Índice vetorial em memória, ranking por item e regra de inserção."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

from scanner.calibracao import Escala
from scanner.embedding import DIMENSAO


@dataclass(frozen=True)
class Resultado:
    item_id: int
    imagem_id: int
    caminho: Path  # imagem do item mais parecida com o scan
    cosseno: float
    porcentagem: float


class Indice:
    """Matriz (N, 384) com todos os vetores de imagem e o item de cada linha."""

    def __init__(self, imagem_ids=None, item_ids=None, matriz=None, caminhos=None):
        self._trava = threading.RLock()
        self._imagem_ids = np.asarray(imagem_ids if imagem_ids is not None else [], np.int64)
        self._item_ids = np.asarray(item_ids if item_ids is not None else [], np.int64)
        self._matriz = (
            np.asarray(matriz, np.float32).reshape(-1, DIMENSAO)
            if matriz is not None
            else np.zeros((0, DIMENSAO), np.float32)
        )
        self._caminhos = list(caminhos or [])

    @classmethod
    def carregar(cls, catalogo) -> "Indice":
        v = catalogo.vetores()
        return cls(v.imagem_ids, v.item_ids, v.matriz, v.caminhos)

    def __len__(self) -> int:
        return len(self._imagem_ids)

    @property
    def total_itens(self) -> int:
        with self._trava:
            return len(np.unique(self._item_ids))

    def contem_item(self, item_id: int) -> bool:
        with self._trava:
            return bool(np.any(self._item_ids == item_id))

    def adicionar(self, item, vetores: np.ndarray) -> None:
        """Acrescenta as imagens de um item recém-inserido (na ordem de item.imagens)."""
        vetores = np.asarray(vetores, np.float32).reshape(-1, DIMENSAO)
        if len(vetores) != len(item.imagens):
            raise ValueError("número de vetores diferente do número de imagens do item")
        with self._trava:
            self._imagem_ids = np.concatenate([self._imagem_ids, [i.id for i in item.imagens]])
            self._item_ids = np.concatenate([self._item_ids, [item.id] * len(item.imagens)])
            self._matriz = np.concatenate([self._matriz, vetores])
            self._caminhos.extend(i.caminho for i in item.imagens)

    def remover(self, item_id: int) -> None:
        with self._trava:
            manter = self._item_ids != item_id
            self._imagem_ids = self._imagem_ids[manter]
            self._item_ids = self._item_ids[manter]
            self._matriz = self._matriz[manter]
            self._caminhos = [c for c, m in zip(self._caminhos, manter) if m]

    def buscar(self, vetor: np.ndarray, escala: Escala, top: int = 10) -> list[Resultado]:
        """Top itens por similaridade. Cada item aparece uma vez, com sua melhor imagem."""
        with self._trava:
            if len(self._imagem_ids) == 0:
                return []
            sims = self._matriz @ np.asarray(vetor, np.float32)
            ordem = np.argsort(-sims, kind="stable")
            # Primeira ocorrência de cada item na ordem decrescente = sua melhor imagem.
            _, primeira = np.unique(self._item_ids[ordem], return_index=True)
            melhores = ordem[np.sort(primeira)][:top]
            return [
                Resultado(
                    int(self._item_ids[k]),
                    int(self._imagem_ids[k]),
                    self._caminhos[k],
                    float(sims[k]),
                    escala(float(sims[k])),
                )
                for k in melhores
            ]


class Decisao(Enum):
    DESCARTAR = "descartar"
    INSERIR = "inserir"
    PEDIR_CONSENTIMENTO = "pedir_consentimento"


def decidir_insercao(
    resultados: list[Resultado], contem_rosto: bool, limiar: float = 90.0
) -> Decisao:
    """1º colocado >= limiar: descarta. Abaixo (ou catálogo vazio): insere,
    pedindo consentimento antes quando o scan contém rosto."""
    if resultados and resultados[0].porcentagem >= limiar:
        return Decisao.DESCARTAR
    return Decisao.PEDIR_CONSENTIMENTO if contem_rosto else Decisao.INSERIR
