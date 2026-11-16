import cv2
import numpy as np

from scanner.qualidade import avaliar


def test_imagem_nitida_e_valida(cfg, img_objeto):
    q = avaliar(img_objeto, cfg.qualidade)
    assert q.valido
    assert q.motivo is None
    assert q.pontuacao > 1.0


def test_imagem_borrada_e_descartada(cfg, img_objeto):
    borrada = cv2.GaussianBlur(img_objeto, (9, 9), 0)
    q = avaliar(borrada, cfg.qualidade)
    assert not q.valido
    assert q.motivo == "borrado"


def test_imagem_escura_e_descartada(cfg, img_objeto):
    escura = (img_objeto * 0.12).astype(np.uint8)
    q = avaliar(escura, cfg.qualidade)
    assert not q.valido
    assert q.motivo == "escuro demais"


def test_imagem_estourada_e_descartada(cfg):
    branca = np.full((480, 640, 3), 250, np.uint8)
    q = avaliar(branca, cfg.qualidade)
    assert not q.valido
    assert q.motivo == "claro demais"


def test_pontuacao_ordena_por_nitidez(cfg, img_objeto):
    nitida = avaliar(img_objeto, cfg.qualidade)
    leve = avaliar(cv2.GaussianBlur(img_objeto, (3, 3), 0), cfg.qualidade)
    assert nitida.pontuacao > leve.pontuacao
