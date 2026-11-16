"""Adição manual de imagens (7.1): arquivos escolhidos viram um item guardado como um scan."""

import cv2
import pytest

from scanner.captura import ProcessadorFrames
from scanner.catalogo import PADRAO_NOME_SCAN, Catalogo
from scanner.config import carregar_config
from scanner.motor import Motor
from scanner.ranking import Indice
from tests.conftest import RAIZ, ler, requer_modelos
from tests.seed_exemplo import variacoes

pytestmark = requer_modelos


@pytest.fixture(scope="module")
def processador():
    return ProcessadorFrames.criar(carregar_config(RAIZ / "config.toml"))


@pytest.fixture
def motor(tmp_path, processador):
    cfg = carregar_config(RAIZ / "config.toml")
    cfg.catalogo.diretorio_dados = tmp_path / "data"
    cat = Catalogo(cfg.catalogo.diretorio_dados)
    m = Motor(cfg, processador, cat, Indice.carregar(cat))
    yield m
    m.fechar()


def _gravar(pasta, nome, img):
    pasta.mkdir(exist_ok=True)
    caminho = pasta / nome
    cv2.imwrite(str(caminho), img)
    return caminho


def _canecas(tmp_path, n=3):
    return [
        _gravar(tmp_path / "escolhidas", f"caneca{i}.png", v)
        for i, v in enumerate(variacoes(ler("coffee.png"), n, semente=5))
    ]


def test_imagens_validas_viram_um_item_guardado_como_scan(motor, tmp_path):
    caminhos = _canecas(tmp_path)
    r = motor.adicionar_imagens(caminhos)
    assert r.ignoradas == [] and r.adicionadas == 3
    item = r.item
    assert item.origem == "scan" and PADRAO_NOME_SCAN.match(item.nome)
    pasta = motor.catalogo.dir_imagens / item.nome
    assert sorted(p.name for p in pasta.iterdir()) == ["1.jpg", "2.jpg", "3.jpg"]
    assert all(img.caminho.exists() for img in item.imagens)
    assert motor.indice.contem_item(item.id) and motor.indice.total_itens == 1
    # Removível como qualquer item criado pelo aplicativo.
    assert [i.id for i in motor.itens_scan()] == [item.id]


def test_imagens_invalidas_sao_ignoradas_com_motivo(motor, tmp_path):
    caminhos = _canecas(tmp_path, 2)
    borrada = _gravar(tmp_path / "escolhidas", "borrada.png", cv2.GaussianBlur(ler("coffee.png"), (31, 31), 0))
    texto = tmp_path / "escolhidas" / "notas.png"
    texto.write_text("isto não é uma imagem")
    r = motor.adicionar_imagens([*caminhos, borrada, texto])
    assert r.adicionadas == 2
    assert r.ignoradas == [("borrada.png", "borrado"), ("notas.png", "não é uma imagem legível")]


def test_nenhuma_imagem_valida_nao_grava_nada(motor, tmp_path):
    borrada = _gravar(tmp_path / "escolhidas", "borrada.png", cv2.GaussianBlur(ler("coffee.png"), (31, 31), 0))
    r = motor.adicionar_imagens([borrada, tmp_path / "nao-existe.jpg"])
    assert r.item is None and r.adicionadas == 0
    assert [m for _, m in r.ignoradas] == ["borrado", "não é uma imagem legível"]
    assert motor.catalogo.total_itens() == 0
    assert list(motor.catalogo.dir_imagens.iterdir()) == []


def test_imagens_repetidas_entram_sem_regra_dos_90(motor, tmp_path):
    caminhos = _canecas(tmp_path)
    primeiro = motor.adicionar_imagens(caminhos).item
    segundo = motor.adicionar_imagens(caminhos).item  # 100% parecidas com o primeiro
    assert segundo is not None and segundo.id != primeiro.id
    assert motor.catalogo.total_itens() == 2


def test_imagem_com_rosto_entra_sem_consentimento(motor, tmp_path):
    rosto = _gravar(tmp_path / "escolhidas", "astronauta.png", ler("astronaut.png"))
    r = motor.adicionar_imagens([rosto])
    assert r.item is not None and r.adicionadas == 1


def test_caminho_com_acentos(motor, tmp_path):
    caminho = _gravar(tmp_path / "fotos-ação", "caneca-é.png", ler("coffee.png"))
    assert motor.adicionar_imagens([caminho]).adicionadas == 1
