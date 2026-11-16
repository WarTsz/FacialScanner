import cv2
import numpy as np
import pytest

from scanner.captura import (
    FalhaScan,
    FonteCamera,
    FonteIndisponivel,
    FrameProcessado,
    ProcessadorFrames,
    agregar,
    instantes_amostragem,
)
from scanner.embedding import normalizar
from scanner.qualidade import Qualidade
from scanner.recorte import recortar_moldura
from tests.conftest import DADOS, ler, requer_modelos


def _frame(vetor, rosto=False, pontuacao=1.0, valido=True):
    q = Qualidade(10.0, 100.0, pontuacao, valido, None if valido else "borrado")
    return FrameProcessado(
        q,
        valido,
        q.motivo,
        tem_rosto=rosto,
        recorte=np.zeros((4, 4, 3), np.uint8) if valido else None,
        vetor=normalizar(np.asarray(vetor, np.float32)) if valido else None,
    )


def test_instantes_distribuidos_na_janela():
    t = instantes_amostragem(15, 5.0)
    assert len(t) == 15
    assert 0 < t[0] < t[-1] < 5.0
    assert np.allclose(np.diff(t), 5.0 / 15)


def test_scan_de_rosto_por_maioria():
    frames = [_frame([1, 0, 0], rosto=True)] * 4 + [_frame([0, 1, 0])] * 2
    scan = agregar(frames, minimo=5)
    assert scan.contem_rosto
    assert len(scan.frames) == 4  # só a classe majoritária entra
    assert np.allclose(scan.vetor, [1, 0, 0])


def test_scan_de_objeto_por_maioria_e_empate():
    frames = [_frame([1, 0, 0], rosto=True)] * 3 + [_frame([0, 1, 0])] * 3
    scan = agregar(frames, minimo=5)
    assert not scan.contem_rosto
    assert np.allclose(scan.vetor, [0, 1, 0])


def test_vetor_agregado_e_media_normalizada():
    frames = [_frame([1, 0, 0]), _frame([0, 1, 0])] * 3
    scan = agregar(frames, minimo=5)
    assert np.isclose(np.linalg.norm(scan.vetor), 1.0)
    assert np.allclose(scan.vetor, normalizar(np.array([1, 1, 0], np.float32)))


def test_frames_insuficientes_falham():
    frames = [_frame([1, 0, 0])] * 4 + [_frame(None, valido=False)] * 11
    with pytest.raises(FalhaScan) as exc:
        agregar(frames, minimo=5)
    assert exc.value.validos == 4
    assert exc.value.motivos["borrado"] == 11


def test_melhores_frames_por_pontuacao():
    frames = [_frame([1, 0, 0], pontuacao=p) for p in (1.0, 5.0, 3.0, 2.0, 4.0)]
    scan = agregar(frames, minimo=5)
    assert [f.qualidade.pontuacao for f in scan.melhores(3)] == [5.0, 4.0, 3.0]


def test_fonte_pasta_de_imagens_em_ciclo():
    from scanner.captura import EXTENSOES_IMAGEM

    n = sum(1 for p in DADOS.iterdir() if p.suffix.lower() in EXTENSOES_IMAGEM)
    fonte = FonteCamera(str(DADOS))
    primeiras = [fonte.ler() for _ in range(n + 1)]
    assert all(f is not None for f in primeiras)
    assert np.array_equal(primeiras[0], primeiras[n])  # volta à primeira


def test_fonte_inexistente():
    with pytest.raises(FonteIndisponivel):
        FonteCamera(99)


# --- com modelos reais ---


@pytest.fixture(scope="module")
def processador():
    from scanner.config import carregar_config
    from tests.conftest import RAIZ

    return ProcessadorFrames.criar(carregar_config(RAIZ / "config.toml"))


@requer_modelos
def test_processa_frame_de_rosto(processador, img_rosto):
    fp = processador.processar(img_rosto)
    assert fp.valido and fp.tem_rosto
    assert fp.vetor.shape == (384,)


@requer_modelos
def test_processa_frame_de_objeto(processador, img_objeto):
    fp = processador.processar(img_objeto)
    assert fp.valido and not fp.tem_rosto
    assert fp.recorte.shape[:2] == (256, 256)


@requer_modelos
def test_frame_borrado_nao_gera_vetor(processador, img_objeto):
    fp = processador.processar(cv2.GaussianBlur(img_objeto, (21, 21), 0))
    assert not fp.valido and fp.vetor is None


@requer_modelos
def test_scan_real_de_objeto(processador):
    img = ler("coffee.png")
    frames = [
        processador.processar(cv2.convertScaleAbs(img, alpha=1 + i / 50, beta=i))
        for i in range(6)
    ]
    scan = agregar(frames, minimo=5)
    assert not scan.contem_rosto
    assert scan.validos == 6


def _cena_objeto_com_rosto_fora() -> np.ndarray:
    """Caneca dentro da moldura e um rosto visível fora dela."""
    from scanner.recorte import regiao_moldura

    cena = np.full((720, 1280, 3), 120, np.uint8)
    x, y, lado = regiao_moldura(720, 1280, 0.6)
    cena[y : y + lado, x : x + lado] = cv2.resize(ler("coffee.png"), (lado, lado))
    cena[100:440, 0:300] = ler("astronaut.png")[0:340, 60:360]
    return cena


@requer_modelos
def test_scan_ignora_rosto_fora_da_moldura(processador):
    """O sujeito do scan é o que está enquadrado na tela, não um rosto ao lado."""
    cena = _cena_objeto_com_rosto_fora()
    assert processador.detector.maior(cena) is not None  # há um rosto na cena
    fp = processador.processar(cena, rosto_na_moldura=True)
    assert fp.valido and not fp.tem_rosto
    np.testing.assert_array_equal(fp.recorte, recortar_moldura(cena, 0.6))


@requer_modelos
def test_scan_ignora_rosto_pequeno_fora_da_moldura(processador):
    """Um rosto pequeno ao fundo, fora da moldura, não invalida o frame do objeto."""
    from scanner.recorte import regiao_moldura

    cena = np.full((480, 640, 3), 120, np.uint8)
    x, y, lado = regiao_moldura(480, 640, 0.6)
    cena[y : y + lado, x : x + lado] = cv2.resize(ler("coffee.png"), (lado, lado))
    cena[0:170, 0:150] = cv2.resize(ler("astronaut.png")[0:340, 60:360], (150, 170))
    assert processador.processar(cena).motivo == "rosto pequeno demais"  # sem a restrição
    fp = processador.processar(cena, rosto_na_moldura=True)
    assert fp.valido and not fp.tem_rosto


@requer_modelos
def test_rosto_dentro_da_moldura_continua_sendo_rosto(processador, img_rosto):
    fp = processador.processar(img_rosto, rosto_na_moldura=True)
    assert fp.valido and fp.tem_rosto


@requer_modelos
def test_seed_continua_usando_a_imagem_inteira(processador):
    """Sem moldura na tela (seed), qualquer rosto da imagem vale, como antes."""
    fp = processador.processar(_cena_objeto_com_rosto_fora(), fracao_moldura=1.0)
    assert fp.tem_rosto
