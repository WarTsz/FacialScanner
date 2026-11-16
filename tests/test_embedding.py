import time

import cv2
import numpy as np
import pytest

from scanner.embedding import DIMENSAO, Embedder
from scanner.modelos import caminho_dino
from scanner.recorte import recortar_moldura
from tests.conftest import ler, requer_modelos

pytestmark = requer_modelos


@pytest.fixture(scope="module")
def embedder():
    from scanner.config import carregar_config
    from tests.conftest import RAIZ

    return Embedder(caminho_dino(carregar_config(RAIZ / "config.toml")), dispositivo="cpu")


def test_dimensao_e_norma(embedder, img_objeto):
    v = embedder.vetorizar([recortar_moldura(img_objeto, 1.0)])
    assert v.shape == (1, DIMENSAO)
    assert v.dtype == np.float32
    assert np.isclose(np.linalg.norm(v[0]), 1.0, atol=1e-5)


def test_mesma_imagem_mesmo_vetor(embedder, img_objeto):
    r = recortar_moldura(img_objeto, 1.0)
    a = embedder.vetorizar_um(r)
    b = embedder.vetorizar_um(r.copy())
    assert np.allclose(a, b, atol=1e-5)


def test_lote_igual_a_individual(embedder):
    recortes = [recortar_moldura(ler(n), 1.0) for n in ("coffee.png", "chelsea.png")]
    lote = embedder.vetorizar(recortes)
    assert np.allclose(lote[1], embedder.vetorizar_um(recortes[1]), atol=1e-4)


def test_variacao_do_mesmo_objeto_e_mais_proxima_que_outro_objeto(embedder, img_objeto):
    base = recortar_moldura(img_objeto, 1.0)
    variacao = cv2.convertScaleAbs(recortar_moldura(img_objeto, 0.9), alpha=1.1, beta=10)
    outro = recortar_moldura(ler("rocket.jpg"), 1.0)
    vb, vv, vo = embedder.vetorizar([base, variacao, outro])
    assert float(vb @ vv) > float(vb @ vo)


def test_lista_vazia(embedder):
    assert embedder.vetorizar([]).shape == (0, DIMENSAO)


def test_tempo_por_imagem_em_cpu(embedder, img_objeto):
    r = recortar_moldura(img_objeto, 1.0)
    embedder.vetorizar_um(r)  # aquecimento
    t0 = time.perf_counter()
    for _ in range(5):
        embedder.vetorizar_um(r)
    assert (time.perf_counter() - t0) / 5 < 0.3
