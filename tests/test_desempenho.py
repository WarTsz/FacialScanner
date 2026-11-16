"""4.6: tempo entre o fim da captura e o ranking, com 10.000 itens, em CPU."""

import time

import numpy as np

from scanner.calibracao import Escala
from scanner.captura import ProcessadorFrames
from scanner.config import carregar_config
from scanner.embedding import DIMENSAO, Embedder, normalizar
from scanner.modelos import caminho_dino, caminho_yunet
from scanner.motor import Motor
from scanner.ranking import Indice
from scanner.recorte import DetectorRosto
from tests.conftest import RAIZ, ler, requer_modelos

N_ITENS = 10_000
POR_ITEM = 5


@requer_modelos
def test_ranking_em_ate_2s_com_10mil_itens_em_cpu(capsys):
    cfg = carregar_config(RAIZ / "config.toml")
    processador = ProcessadorFrames(
        cfg,
        DetectorRosto(caminho_yunet(cfg), cfg.qualidade.rosto_confianca_min),
        Embedder(caminho_dino(cfg), dispositivo="cpu"),
    )
    rng = np.random.default_rng(0)
    n = N_ITENS * POR_ITEM
    indice = Indice(
        np.arange(n),
        np.repeat(np.arange(N_ITENS), POR_ITEM),
        normalizar(rng.normal(size=(n, DIMENSAO))),
        [f"{i}.jpg" for i in range(n)],
    )
    motor = Motor(cfg, processador, catalogo=None, indice=indice)

    img = ler("astronaut.png")
    # Frames processados durante a janela (fora da medição), como na GUI.
    frames = [processador.processar(img) for _ in range(cfg.captura.n_frames - 1)]
    processador.processar(img)  # aquecimento

    t0 = time.perf_counter()
    frames.append(processador.processar(img))  # último frame ainda na fila
    resultado = motor.concluir(frames)
    dt = time.perf_counter() - t0

    with capsys.disabled():
        print(f"\n  fim da captura -> ranking: {dt * 1000:.0f} ms ({n} vetores, CPU)")
    assert len(resultado.resultados) == cfg.ranking.top
    assert dt < 2.0
