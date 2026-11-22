"""Agrupamento por semelhança mínima e escolha do grupo (8.1)."""

import numpy as np

from scanner.calibracao import Escala
from scanner.comparacao import agrupar_por_semelhanca, escolher_grupo
from scanner.config import carregar_config
from scanner.embedding import DIMENSAO, normalizar
from tests.conftest import RAIZ

ESCALA = Escala(0.0, 0.7)


def _objeto(semente):
    return normalizar(np.random.default_rng(semente).normal(size=DIMENSAO))


def _foto(centro, semente, ruido=0.3):
    """Variação de um objeto: perto do centro (cos ~0.95), longe de outros objetos (cos ~0)."""
    rng = np.random.default_rng(1000 + semente)
    return normalizar(centro + ruido * normalizar(rng.normal(size=DIMENSAO)))


def test_imagens_semelhantes_formam_um_grupo():
    caneca = _objeto(1)
    v = [_foto(caneca, i) for i in range(4)]
    assert agrupar_por_semelhanca(v, ESCALA, 50.0) == [[0, 1, 2, 3]]


def test_imagem_diferente_fica_em_outro_grupo():
    caneca, foguete = _objeto(1), _objeto(2)
    v = [_foto(caneca, 0), _foto(caneca, 1), _foto(foguete, 2), _foto(caneca, 3)]
    grupos = agrupar_por_semelhanca(v, ESCALA, 50.0)
    assert grupos == [[0, 1, 3], [2]]
    assert escolher_grupo(grupos) == 0


def test_maior_grupo_vence_mesmo_formado_depois():
    caneca, foguete = _objeto(1), _objeto(2)
    v = [_foto(foguete, 0), _foto(caneca, 1), _foto(caneca, 2), _foto(caneca, 3)]
    grupos = agrupar_por_semelhanca(v, ESCALA, 50.0)
    assert grupos == [[0], [1, 2, 3]]
    assert escolher_grupo(grupos) == 1


def test_empate_escolhe_o_primeiro_grupo_formado():
    caneca, foguete = _objeto(1), _objeto(2)
    v = [_foto(foguete, 0), _foto(caneca, 1), _foto(caneca, 2), _foto(foguete, 3)]
    grupos = agrupar_por_semelhanca(v, ESCALA, 50.0)
    assert grupos == [[0, 3], [1, 2]]
    assert escolher_grupo(grupos) == 0


def test_tres_objetos_diferentes_viram_tres_grupos():
    v = [_foto(_objeto(s), s) for s in (1, 2, 3)]
    grupos = agrupar_por_semelhanca(v, ESCALA, 50.0)
    assert grupos == [[0], [1], [2]]
    assert escolher_grupo(grupos) == 0


def test_minimo_configuravel():
    caneca = _objeto(1)
    a = _foto(caneca, 0, ruido=0.3)
    b = _foto(caneca, 1, ruido=1.2)  # bem mais distante
    pct = ESCALA(float(a @ b))
    assert 0 < pct < 100
    assert agrupar_por_semelhanca([a, b], ESCALA, pct - 5) == [[0, 1]]
    assert agrupar_por_semelhanca([a, b], ESCALA, pct + 5) == [[0], [1]]


def test_lista_vazia():
    assert agrupar_por_semelhanca(np.zeros((0, DIMENSAO)), ESCALA, 50.0) == []
    assert escolher_grupo([]) is None


def test_minimo_padrao_no_config():
    assert carregar_config(RAIZ / "config.toml").comparacao.similaridade_minima == 50.0
