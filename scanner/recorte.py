"""Detecção de rosto (YuNet) e recorte do sujeito: rosto alinhado ou região da moldura."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)

TAMANHO_RECORTE = 256
MARGEM_ROSTO = 0.2


@dataclass(frozen=True)
class Rosto:
    caixa: tuple[float, float, float, float]  # x, y, largura, altura
    olho_a: tuple[float, float]  # olho que aparece à esquerda na imagem
    olho_b: tuple[float, float]  # olho que aparece à direita na imagem
    confianca: float

    @property
    def lado(self) -> float:
        return min(self.caixa[2], self.caixa[3])

    @property
    def centro(self) -> tuple[float, float]:
        x, y, w, h = self.caixa
        return x + w / 2, y + h / 2

    @property
    def area(self) -> float:
        return self.caixa[2] * self.caixa[3]


class DetectorRosto:
    """Wrapper do YuNet. Não é thread-safe: use uma instância por thread."""

    def __init__(self, caminho_modelo: Path, confianca_min: float = 0.8):
        self._det = cv2.FaceDetectorYN.create(
            str(caminho_modelo), "", (320, 320), confianca_min, 0.3, 50
        )

    def detectar(self, img_bgr: np.ndarray) -> list[Rosto]:
        h, w = img_bgr.shape[:2]
        self._det.setInputSize((w, h))
        _, faces = self._det.detect(img_bgr)
        if faces is None:
            return []
        rostos = []
        for f in faces:
            olhos = sorted([(float(f[4]), float(f[5])), (float(f[6]), float(f[7]))])
            rostos.append(
                Rosto(
                    caixa=(float(f[0]), float(f[1]), float(f[2]), float(f[3])),
                    olho_a=olhos[0],
                    olho_b=olhos[1],
                    confianca=float(f[14]),
                )
            )
        rostos.sort(key=lambda r: r.area, reverse=True)
        return rostos

    def maior(self, img_bgr: np.ndarray) -> Rosto | None:
        rostos = self.detectar(img_bgr)
        return rostos[0] if rostos else None


def recortar_rosto(
    img_bgr: np.ndarray,
    rosto: Rosto,
    margem: float = MARGEM_ROSTO,
    tamanho: int = TAMANHO_RECORTE,
) -> np.ndarray:
    """Recorte quadrado do rosto, com margem e girado para deixar os olhos na horizontal."""
    (ax, ay), (bx, by) = rosto.olho_a, rosto.olho_b
    angulo = math.degrees(math.atan2(by - ay, bx - ax))
    cx, cy = rosto.centro
    lado = max(rosto.caixa[2], rosto.caixa[3]) * (1 + 2 * margem)
    m = cv2.getRotationMatrix2D((cx, cy), angulo, tamanho / lado)
    m[0, 2] += tamanho / 2 - cx
    m[1, 2] += tamanho / 2 - cy
    return cv2.warpAffine(
        img_bgr, m, (tamanho, tamanho), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )


def regiao_moldura(altura: int, largura: int, fracao: float) -> tuple[int, int, int]:
    """Quadrado central (x, y, lado) com lado = fracao * menor dimensão."""
    lado = max(1, round(min(altura, largura) * fracao))
    x = (largura - lado) // 2
    y = (altura - lado) // 2
    return x, y, lado


def rostos_na_moldura(
    rostos: list[Rosto], altura: int, largura: int, fracao: float
) -> list[Rosto]:
    """Só os rostos cujo centro fica dentro da moldura exibida na tela (ordem mantida)."""
    x, y, lado = regiao_moldura(altura, largura, fracao)
    return [
        r for r in rostos if x <= r.centro[0] <= x + lado and y <= r.centro[1] <= y + lado
    ]


def recortar_moldura(
    img_bgr: np.ndarray, fracao: float, tamanho: int = TAMANHO_RECORTE
) -> np.ndarray:
    """Recorte da região da moldura. fracao=1.0 usa o maior quadrado central."""
    h, w = img_bgr.shape[:2]
    x, y, lado = regiao_moldura(h, w, fracao)
    regiao = img_bgr[y : y + lado, x : x + lado]
    interp = cv2.INTER_AREA if lado > tamanho else cv2.INTER_LINEAR
    return cv2.resize(regiao, (tamanho, tamanho), interpolation=interp)
