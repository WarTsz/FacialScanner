import math

import cv2
import numpy as np
import pytest

from scanner.modelos import caminho_yunet
from scanner.recorte import (
    TAMANHO_RECORTE,
    DetectorRosto,
    Rosto,
    recortar_moldura,
    recortar_rosto,
    regiao_moldura,
    rostos_na_moldura,
)
from tests.conftest import requer_modelos


def _rosto_em(cx, cy, lado=100):
    return Rosto((cx - lado / 2, cy - lado / 2, lado, lado), (cx - 20, cy), (cx + 20, cy), 0.9)


def test_rostos_na_moldura_usa_o_centro_do_rosto():
    # Frame 640x480, moldura 0.6: quadrado (176, 96) com lado 288.
    dentro = _rosto_em(320, 240)
    na_borda = _rosto_em(180, 100)  # centro dentro, caixa saindo da moldura
    fora = _rosto_em(80, 60)  # ex.: rosto de quem segura o objeto, acima e ao lado
    rostos = [fora, dentro, na_borda]
    assert rostos_na_moldura(rostos, 480, 640, 0.6) == [dentro, na_borda]
    assert rostos_na_moldura([fora], 480, 640, 0.6) == []


@pytest.fixture
def detector(cfg):
    return DetectorRosto(caminho_yunet(cfg), cfg.qualidade.rosto_confianca_min)


# --- detecção (2.2) ---


@requer_modelos
def test_detecta_rosto(detector, img_rosto, cfg):
    rosto = detector.maior(img_rosto)
    assert rosto is not None
    assert rosto.confianca >= cfg.qualidade.rosto_confianca_min
    assert rosto.lado >= cfg.qualidade.rosto_lado_min_px


@requer_modelos
def test_objeto_sem_rosto(detector, img_objeto):
    assert detector.maior(img_objeto) is None
    assert detector.detectar(cv2.imread("tests/data/rocket.jpg")) == []


@requer_modelos
def test_rosto_pequeno_fica_abaixo_do_minimo(detector, img_rosto, cfg):
    pequeno = cv2.resize(img_rosto, (128, 128))
    tela = np.full((480, 640, 3), 128, np.uint8)
    tela[100:228, 100:228] = pequeno
    rosto = detector.maior(tela)
    assert rosto is None or rosto.lado < cfg.qualidade.rosto_lado_min_px


# --- recorte (2.3) ---


@requer_modelos
def test_recorte_rosto_dimensoes_e_centralizado(detector, img_rosto):
    rosto = detector.maior(img_rosto)
    recorte = recortar_rosto(img_rosto, rosto)
    assert recorte.shape == (TAMANHO_RECORTE, TAMANHO_RECORTE, 3)
    # O rosto continua detectável e ocupa o centro do recorte, com margem.
    novo = detector.maior(recorte)
    assert novo is not None
    cx, cy = novo.centro
    assert abs(cx - TAMANHO_RECORTE / 2) < TAMANHO_RECORTE * 0.12
    assert abs(cy - TAMANHO_RECORTE / 2) < TAMANHO_RECORTE * 0.12
    assert novo.caixa[2] < TAMANHO_RECORTE * 0.85


def _centroide(img, canal):
    mascara = (img[..., canal] > 200) & (img[..., (canal + 1) % 3] < 80)
    ys, xs = np.nonzero(mascara)
    return xs.mean(), ys.mean()


@pytest.mark.parametrize("inclinacao", [-25, -10, 10, 25])
def test_recorte_rosto_alinha_olhos(inclinacao):
    # Olhos sintéticos inclinados: o recorte deve deixá-los na horizontal.
    # (Os landmarks do YuNet acompanham pouco a rotação, por isso o teste
    # valida a geometria com pontos conhecidos.)
    img = np.full((400, 400, 3), 128, np.uint8)
    cx, cy, r = 200.0, 200.0, 40.0
    t = math.radians(inclinacao)
    a = (cx - r * math.cos(t), cy - r * math.sin(t))
    b = (cx + r * math.cos(t), cy + r * math.sin(t))
    cv2.circle(img, (round(a[0]), round(a[1])), 6, (255, 0, 0), -1)  # azul
    cv2.circle(img, (round(b[0]), round(b[1])), 6, (0, 255, 0), -1)  # verde
    rosto = Rosto(caixa=(140, 140, 120, 120), olho_a=a, olho_b=b, confianca=0.9)

    recorte = recortar_rosto(img, rosto)
    assert recorte.shape == (TAMANHO_RECORTE, TAMANHO_RECORTE, 3)
    (ax, ay), (bx, by) = _centroide(recorte, 0), _centroide(recorte, 1)
    assert abs(math.degrees(math.atan2(by - ay, bx - ax))) < 2
    assert ax < bx
    # Centro do rosto vai para o centro do recorte.
    assert abs((ax + bx) / 2 - TAMANHO_RECORTE / 2) < 3
    assert abs((ay + by) / 2 - TAMANHO_RECORTE / 2) < 3


def test_regiao_moldura_central():
    x, y, lado = regiao_moldura(480, 640, 0.6)
    assert lado == 288
    assert (x, y) == ((640 - 288) // 2, (480 - 288) // 2)


def test_recorte_moldura_pega_so_a_regiao():
    img = np.zeros((480, 640, 3), np.uint8)
    img[:] = (0, 0, 255)  # fora da moldura: vermelho
    x, y, lado = regiao_moldura(480, 640, 0.6)
    img[y : y + lado, x : x + lado] = (255, 0, 0)  # moldura: azul
    recorte = recortar_moldura(img, 0.6)
    assert recorte.shape == (TAMANHO_RECORTE, TAMANHO_RECORTE, 3)
    assert (recorte[..., 0] > 250).all() and (recorte[..., 2] < 5).all()


def test_recorte_moldura_fracao_1_usa_quadrado_central():
    img = np.zeros((300, 500, 3), np.uint8)
    img[:, 100:400] = 255
    recorte = recortar_moldura(img, 1.0)
    assert recorte.shape == (TAMANHO_RECORTE, TAMANHO_RECORTE, 3)
    assert (recorte > 250).all()
