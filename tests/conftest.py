import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import cv2
import numpy as np
import pytest

from scanner.config import Config, carregar_config
from scanner.modelos import caminho_dino, caminho_yunet

DADOS = Path(__file__).parent / "data"
RAIZ = Path(__file__).resolve().parent.parent


def ler(nome: str) -> np.ndarray:
    img = cv2.imread(str(DADOS / nome))
    assert img is not None, nome
    return img


@pytest.fixture
def cfg() -> Config:
    return carregar_config(RAIZ / "config.toml")


def _modelos_presentes() -> bool:
    c = carregar_config(RAIZ / "config.toml")
    return caminho_yunet(c).exists() and caminho_dino(c).exists()


requer_modelos = pytest.mark.skipif(
    not _modelos_presentes(), reason="rode `python -m scanner preparar` antes"
)


@pytest.fixture
def img_rosto() -> np.ndarray:
    return ler("astronaut.png")


@pytest.fixture
def img_objeto() -> np.ndarray:
    return ler("coffee.png")
