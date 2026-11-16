"""Gera uma pasta de seed de exemplo a partir das imagens de teste.

Cada imagem base vira um item com variações (escala, rotação, luz, espelhamento),
simulando fotos diferentes do mesmo item. Uso:

    python -m tests.seed_exemplo <pasta-destino>
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

DADOS = Path(__file__).parent / "data"
ITENS = {
    "astronauta": "astronaut.png",
    "cafe": "coffee.png",
    "gata": "chelsea.png",
    "foguete": "rocket.jpg",
}


def variacoes(img: np.ndarray, n: int, semente: int = 0) -> list[np.ndarray]:
    rng = np.random.default_rng(semente)
    h, w = img.shape[:2]
    saida = [img.copy()]
    while len(saida) < n:
        angulo = rng.uniform(-8, 8)
        escala = rng.uniform(1.0, 1.15)
        dx, dy = rng.uniform(-0.04, 0.04, 2) * (w, h)
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angulo, escala)
        m[:, 2] += (dx, dy)
        v = cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)
        v = cv2.convertScaleAbs(v, alpha=rng.uniform(0.85, 1.15), beta=rng.uniform(-20, 20))
        if rng.random() < 0.5:
            v = cv2.flip(v, 1)
        saida.append(v)
    return saida


def sequencia_camera(img: np.ndarray, n: int, semente: int = 0) -> list[np.ndarray]:
    """Frames de uma webcam filmando um sujeito parado: tremor, ruído e luz leves."""
    rng = np.random.default_rng(semente)
    h, w = img.shape[:2]
    frames = []
    for _ in range(n):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-1.5, 1.5), rng.uniform(1.0, 1.02))
        m[:, 2] += rng.uniform(-0.01, 0.01, 2) * (w, h)
        f = cv2.warpAffine(img, m, (w, h), borderMode=cv2.BORDER_REFLECT)
        f = cv2.convertScaleAbs(f, alpha=rng.uniform(0.95, 1.05), beta=rng.uniform(-6, 6))
        ruido = rng.normal(0, 3, f.shape)
        frames.append(np.clip(f.astype(np.float64) + ruido, 0, 255).astype(np.uint8))
    return frames


def gerar(destino: Path, por_item: int = 5) -> Path:
    destino = Path(destino)
    for i, (nome, arquivo) in enumerate(ITENS.items()):
        pasta = destino / nome
        pasta.mkdir(parents=True, exist_ok=True)
        base = cv2.imread(str(DADOS / arquivo))
        for j, v in enumerate(variacoes(base, por_item, semente=i)):
            cv2.imwrite(str(pasta / f"{j + 1}.jpg"), v)
    return destino


if __name__ == "__main__":
    print(gerar(Path(sys.argv[1] if len(sys.argv) > 1 else "seed-exemplo")))
