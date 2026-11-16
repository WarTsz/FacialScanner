import io
import subprocess
import sys

import cv2
import numpy as np
import pytest

from scanner.captura import ProcessadorFrames
from scanner.catalogo import Catalogo, importar_seed
from tests.conftest import RAIZ, ler, requer_modelos
from tests.seed_exemplo import gerar

pytestmark = requer_modelos


@pytest.fixture(scope="module")
def processador():
    from scanner.config import carregar_config

    return ProcessadorFrames.criar(carregar_config(RAIZ / "config.toml"))


@pytest.fixture
def pasta_seed(tmp_path):
    seed = tmp_path / "seed"
    gerar(seed, por_item=3)
    # Uma imagem inválida (escura) em um item que tem imagens boas.
    cv2.imwrite(str(seed / "cafe" / "escura.jpg"), (ler("coffee.png") * 0.1).astype(np.uint8))
    (seed / "cafe" / "notas.txt").write_text("ignorar")
    # Uma subpasta só com imagens inválidas e outra vazia.
    (seed / "borradas").mkdir()
    cv2.imwrite(str(seed / "borradas" / "1.jpg"), cv2.GaussianBlur(ler("rocket.jpg"), (31, 31), 0))
    (seed / "vazia").mkdir()
    return seed


def test_importa_itens_validos_e_reporta_ignorados(tmp_path, processador, pasta_seed):
    cat = Catalogo(tmp_path / "data")
    saida = io.StringIO()
    criados = importar_seed(cat, processador, pasta_seed, saida=saida)
    texto = saida.getvalue()

    assert sorted(i.nome for i in criados) == ["astronauta", "cafe", "foguete", "gata"]
    assert all(i.origem == "seed" for i in criados)
    cafe = next(i for i in criados if i.nome == "cafe")
    assert len(cafe.imagens) == 3
    assert "cafe/escura.jpg: escuro demais" in texto
    assert "[pulado] borradas: nenhuma imagem válida" in texto
    assert "[pulado] vazia: nenhuma imagem válida" in texto
    assert cat.obter(cafe.id).imagens[0].caminho.exists()
    cat.fechar()


def test_rodar_de_novo_pula_itens_existentes(tmp_path, processador, pasta_seed):
    cat = Catalogo(tmp_path / "data")
    importar_seed(cat, processador, pasta_seed, saida=io.StringIO())
    saida = io.StringIO()
    criados = importar_seed(cat, processador, pasta_seed, saida=saida)
    assert criados == []
    assert "[pulado] cafe: já existe no catálogo" in saida.getvalue()
    assert cat.total_itens() == 4
    cat.fechar()


def test_nome_reservado_e_pulado(tmp_path, processador):
    seed = tmp_path / "seed"
    gerar(seed, por_item=1)
    (seed / "cafe").rename(seed / "item-000001")
    cat = Catalogo(tmp_path / "data")
    saida = io.StringIO()
    criados = importar_seed(cat, processador, seed, saida=saida)
    assert "item-000001" not in [i.nome for i in criados]
    assert "nome reservado" in saida.getvalue()
    cat.fechar()


def test_cli_seed(tmp_path, pasta_seed):
    config = tmp_path / "config.toml"
    config.write_text(
        f'[catalogo]\ndiretorio_dados = "{tmp_path / "data"}"\n'
        f'[modelos]\ndiretorio = "{RAIZ / "models"}"\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, "-m", "scanner", "--config", str(config), "seed", str(pasta_seed)],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )
    assert r.returncode == 0, r.stderr
    assert "Seed concluído: 4 item(ns) criado(s)." in r.stdout
    assert (tmp_path / "data" / "catalogo.db").exists()


def test_cli_seed_pasta_inexistente(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'[catalogo]\ndiretorio_dados = "{tmp_path / "data"}"\n'
        f'[modelos]\ndiretorio = "{RAIZ / "models"}"\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, "-m", "scanner", "--config", str(config), "seed", str(tmp_path / "x")],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )
    assert r.returncode == 1
    assert "não encontrada" in r.stderr
