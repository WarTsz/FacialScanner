"""Calibração: converte o cosseno bruto em uma porcentagem de similaridade."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class ErroCalibracao(RuntimeError):
    pass


@dataclass(frozen=True)
class Escala:
    """Mapeamento linear por partes: cos_zero -> 0%, cos_noventa -> 90%, 1.0 -> 100%."""

    cos_zero: float
    cos_noventa: float

    def __post_init__(self):
        if not (self.cos_zero < self.cos_noventa < 1.0):
            raise ErroCalibracao(
                f"âncoras inválidas: precisa cos_zero < cos_noventa < 1 "
                f"(cos_zero={self.cos_zero}, cos_noventa={self.cos_noventa})"
            )

    def __call__(self, cos):
        c = np.asarray(cos, np.float64)
        baixo = 90.0 * (c - self.cos_zero) / (self.cos_noventa - self.cos_zero)
        alto = 90.0 + 10.0 * (c - self.cos_noventa) / (1.0 - self.cos_noventa)
        pct = np.clip(np.where(c <= self.cos_noventa, baixo, alto), 0.0, 100.0)
        return float(pct) if pct.ndim == 0 else pct


@dataclass(frozen=True)
class ResultadoCalibracao:
    escala: Escala
    iguais: np.ndarray
    diferentes: np.ndarray


def _resumo(v: np.ndarray) -> str:
    p = np.percentile(v, [0, 10, 50, 90, 100])
    return "min {:.3f} | p10 {:.3f} | mediana {:.3f} | p90 {:.3f} | max {:.3f}".format(*p)


def calcular(
    item_ids: np.ndarray, matriz: np.ndarray, max_pares: int = 50_000, semente: int = 0
) -> ResultadoCalibracao:
    """cos_zero = mediana dos pares de itens diferentes; cos_noventa = p10 dos pares iguais."""
    item_ids = np.asarray(item_ids)
    if len(np.unique(item_ids)) < 2:
        raise ErroCalibracao("são necessários pelo menos 2 itens no catálogo")
    sims = matriz @ matriz.T
    i, j = np.triu_indices(len(item_ids), k=1)
    mesmo = item_ids[i] == item_ids[j]
    iguais = sims[i[mesmo], j[mesmo]]
    diferentes = sims[i[~mesmo], j[~mesmo]]
    if len(iguais) == 0:
        raise ErroCalibracao("nenhum item tem 2 ou mais imagens: não há pares 'mesmo item'")
    rng = np.random.default_rng(semente)
    if len(diferentes) > max_pares:
        diferentes = rng.choice(diferentes, max_pares, replace=False)
    if len(iguais) > max_pares:
        iguais = rng.choice(iguais, max_pares, replace=False)
    escala = Escala(float(np.median(diferentes)), float(np.percentile(iguais, 10)))
    return ResultadoCalibracao(escala, iguais, diferentes)


def relatorio(r: ResultadoCalibracao) -> str:
    sobreposicao = float(np.mean(r.diferentes >= r.escala.cos_noventa)) * 100
    return "\n".join(
        [
            f"Pares do mesmo item ({len(r.iguais)}):     {_resumo(r.iguais)}",
            f"Pares de itens diferentes ({len(r.diferentes)}): {_resumo(r.diferentes)}",
            f"cos_zero    = {r.escala.cos_zero:.4f}  (mediana dos pares diferentes -> 0%)",
            f"cos_noventa = {r.escala.cos_noventa:.4f}  (p10 dos pares iguais -> 90%)",
            f"Pares diferentes que chegariam a 90% ou mais: {sobreposicao:.1f}%",
        ]
    )


def comando_calibrar(caminho_config: Path | None) -> int:
    from scanner.catalogo import Catalogo
    from scanner.config import CAMINHO_PADRAO, atualizar_calibracao, carregar_config

    cfg = carregar_config(caminho_config)
    catalogo = Catalogo(cfg.catalogo.diretorio_dados)
    try:
        v = catalogo.vetores()
    finally:
        catalogo.fechar()
    try:
        r = calcular(v.item_ids, v.matriz)
    except ErroCalibracao as exc:
        print(f"Não foi possível calibrar: {exc}", file=sys.stderr)
        return 1
    print(relatorio(r))
    destino = cfg.caminho or CAMINHO_PADRAO
    atualizar_calibracao(destino, r.escala.cos_zero, r.escala.cos_noventa)
    print(f"Âncoras gravadas em {destino}")
    return 0
