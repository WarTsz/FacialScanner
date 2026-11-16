"""Filtro de qualidade de frames: nitidez e brilho."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from scanner.config import QualidadeCfg

LARGURA_REFERENCIA = 640


@dataclass(frozen=True)
class Qualidade:
    nitidez: float
    brilho: float
    # Nitidez normalizada pelo limiar: usada para escolher os k melhores frames.
    pontuacao: float
    valido: bool
    motivo: str | None = None


def _cinza_referencia(img_bgr: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    if w != LARGURA_REFERENCIA:
        nova_altura = max(1, round(h * LARGURA_REFERENCIA / w))
        interp = cv2.INTER_AREA if w > LARGURA_REFERENCIA else cv2.INTER_LINEAR
        img_bgr = cv2.resize(img_bgr, (LARGURA_REFERENCIA, nova_altura), interpolation=interp)
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)


def medir(img_bgr: np.ndarray) -> tuple[float, float]:
    """Retorna (nitidez, brilho): variância do Laplaciano e média de cinza."""
    cinza = _cinza_referencia(img_bgr)
    nitidez = float(cv2.Laplacian(cinza, cv2.CV_64F).var())
    brilho = float(cinza.mean())
    return nitidez, brilho


def avaliar(img_bgr: np.ndarray, cfg: QualidadeCfg) -> Qualidade:
    nitidez, brilho = medir(img_bgr)
    pontuacao = nitidez / cfg.nitidez_min if cfg.nitidez_min > 0 else nitidez
    motivo = None
    if brilho < cfg.brilho_min:
        motivo = "escuro demais"
    elif brilho > cfg.brilho_max:
        motivo = "claro demais"
    elif nitidez < cfg.nitidez_min:
        motivo = "borrado"
    return Qualidade(nitidez, brilho, pontuacao, motivo is None, motivo)
