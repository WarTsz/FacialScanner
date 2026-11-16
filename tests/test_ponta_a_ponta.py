"""6.1: fluxo completo com CLI e interface reais, com pastas de imagens como câmera.

preparar -> seed -> calibrar -> objeto novo -> mesmo objeto de novo ->
rosto recusado -> rosto aceito -> remoção.
"""

import subprocess
import sys

import cv2
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from scanner.catalogo import Catalogo
from scanner.config import carregar_config
from scanner.gui.app import MSG_INSERIDO, Estado, JanelaPrincipal
from tests.conftest import RAIZ, ler, requer_modelos
from tests.seed_exemplo import sequencia_camera, variacoes

pytestmark = requer_modelos
TIMEOUT = 30_000


def _cli(config, *args):
    r = subprocess.run(
        [sys.executable, "-m", "scanner", "--config", str(config), *args],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _pasta(base, nome, imagens):
    p = base / nome
    p.mkdir(parents=True)
    for i, img in enumerate(imagens):
        cv2.imwrite(str(p / f"{i + 1}.jpg"), img)
    return p


def _itens(cfg, origem=None):
    cat = Catalogo(cfg.catalogo.diretorio_dados)
    try:
        return cat.listar(origem)
    finally:
        cat.fechar()


def test_fluxo_completo(tmp_path, qtbot):
    # --- preparar / seed / calibrar pela CLI ---
    config = tmp_path / "config.toml"
    config.write_text(
        (RAIZ / "config.toml")
        .read_text(encoding="utf-8")
        .replace('diretorio = "models"', f'diretorio = "{RAIZ / "models"}"'),
        encoding="utf-8",
    )
    assert "Nada a baixar" in _cli(config, "preparar")

    seed = tmp_path / "seed"
    _pasta(seed, "cafe", variacoes(ler("coffee.png"), 5, semente=1))
    _pasta(seed, "gata", variacoes(ler("chelsea.png"), 5, semente=2))
    assert "Seed concluído: 2 item(ns) criado(s)." in _cli(config, "seed", str(seed))

    antes = carregar_config(config).calibracao
    saida = _cli(config, "calibrar")
    assert "Âncoras gravadas" in saida
    cfg = carregar_config(config)
    assert (cfg.calibracao.cos_zero, cfg.calibracao.cos_noventa) != (
        antes.cos_zero,
        antes.cos_noventa,
    )
    assert cfg.captura.duracao_s == 5.0 and cfg.captura.n_frames == 15

    cameras = tmp_path / "cameras"
    # Cada scan "filma" o sujeito parado; scans diferentes têm sequências diferentes.
    foguete = _pasta(cameras, "foguete", sequencia_camera(ler("rocket.jpg"), 8, semente=3))
    foguete_2 = _pasta(cameras, "foguete-2", sequencia_camera(ler("rocket.jpg"), 8, semente=30))
    rosto = _pasta(cameras, "rosto", sequencia_camera(ler("astronaut.png"), 8, semente=4))

    def scan(fonte):
        j = JanelaPrincipal(cfg, str(fonte))  # Motor.criar real, a partir do config
        qtbot.addWidget(j)
        j.show()
        qtbot.waitUntil(lambda: j.tela_camera.botao_escanear.isEnabled(), timeout=TIMEOUT)
        qtbot.mouseClick(j.tela_camera.botao_escanear, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: j.estado == Estado.RESULTADOS, timeout=TIMEOUT)
        return j

    def fechar(j):
        j.close()

    # --- objeto novo: inserido com aviso ---
    j = scan(foguete)
    res = j.resultado_atual.resultados
    assert len(res) == 2 and res[0].porcentagem < 90
    qtbot.waitUntil(lambda: j.tela_resultados.aviso.isVisible(), timeout=TIMEOUT)
    assert j.tela_resultados.aviso.text() == MSG_INSERIDO
    assert j.dialogo_consentimento is None
    fechar(j)
    assert [i.nome for i in _itens(cfg, "scan")] == ["item-000003"]

    # --- mesmo objeto de novo (condições semelhantes): >= 90%, descartado ---
    j = scan(foguete_2)
    res = j.resultado_atual.resultados
    print(f"\n  re-scan do mesmo objeto: {res[0].porcentagem:.1f}% (cos {res[0].cosseno:.3f})")
    assert res[0].porcentagem >= 90
    assert res[0].item_id == _itens(cfg, "scan")[0].id
    qtbot.wait(500)
    assert not j.tela_resultados.aviso.isVisible()
    assert all("item-" not in l.text() for l in j.findChildren(QLabel))
    fechar(j)
    assert len(_itens(cfg)) == 3

    # --- rosto novo, consentimento recusado: nada é gravado ---
    j = scan(rosto)
    assert j.resultado_atual.scan.contem_rosto
    qtbot.waitUntil(lambda: j.dialogo_consentimento is not None, timeout=TIMEOUT)
    qtbot.mouseClick(j.dialogo_consentimento.botao_cancelar, Qt.MouseButton.LeftButton)
    qtbot.wait(500)
    assert not j.tela_resultados.aviso.isVisible()
    fechar(j)
    assert len(_itens(cfg)) == 3

    # --- rosto novo, consentimento aceito: inserido ---
    j = scan(rosto)
    qtbot.waitUntil(lambda: j.dialogo_consentimento is not None, timeout=TIMEOUT)
    qtbot.mouseClick(j.dialogo_consentimento.botao_ok, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: j.tela_resultados.aviso.isVisible(), timeout=TIMEOUT)
    fechar(j)
    scans = _itens(cfg, "scan")
    assert [i.nome for i in scans] == ["item-000003", "item-000004"]
    rosto_item = scans[1]
    assert len(rosto_item.imagens) == cfg.catalogo.imagens_por_item

    # --- remoção do item de rosto pela interface ---
    j = JanelaPrincipal(cfg, str(foguete))
    qtbot.addWidget(j)
    j.show()
    qtbot.waitUntil(lambda: j.tela_camera.botao_gerenciar.isEnabled(), timeout=TIMEOUT)
    qtbot.mouseClick(j.tela_camera.botao_gerenciar, Qt.MouseButton.LeftButton)
    lista = j.tela_remocao.lista
    assert sorted(lista.item(i).text() for i in range(lista.count())) == [
        "item-000003",
        "item-000004",
    ]
    alvo = next(lista.item(i) for i in range(lista.count()) if lista.item(i).text() == "item-000004")
    lista.setCurrentItem(alvo)
    qtbot.mouseClick(j.tela_remocao.botao_remover, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(j.tela_remocao.confirmacao.botao_ok, Qt.MouseButton.LeftButton)
    fechar(j)
    assert [i.nome for i in _itens(cfg, "scan")] == ["item-000003"]
    assert not (cfg.catalogo.diretorio_dados / "images" / "item-000004").exists()
    assert sorted(i.nome for i in _itens(cfg, "seed")) == ["cafe", "gata"]

    # Depois da remoção, um novo scan do mesmo rosto volta a ser "novo".
    j = scan(rosto)
    assert all(r.item_id != rosto_item.id for r in j.resultado_atual.resultados)
    qtbot.waitUntil(lambda: j.dialogo_consentimento is not None, timeout=TIMEOUT)
    qtbot.mouseClick(j.dialogo_consentimento.botao_cancelar, Qt.MouseButton.LeftButton)
    fechar(j)
