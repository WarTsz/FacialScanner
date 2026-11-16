import numpy as np
import pytest

from scanner.captura import FrameProcessado, Scan
from scanner.catalogo import Catalogo, ErroCatalogo, ImagemNova, imagens_do_scan
from scanner.embedding import DIMENSAO, normalizar
from scanner.qualidade import Qualidade


def _img(semente=0, qualidade=1.0) -> ImagemNova:
    rng = np.random.default_rng(semente)
    recorte = rng.integers(0, 255, (256, 256, 3), dtype=np.uint8)
    return ImagemNova(recorte, normalizar(rng.normal(size=DIMENSAO)), qualidade)


@pytest.fixture
def catalogo(tmp_path):
    c = Catalogo(tmp_path / "data")
    yield c
    c.fechar()


# --- 3.1 esquema e persistência ---


def test_banco_criado_e_reaberto_sem_perda(tmp_path):
    c = Catalogo(tmp_path / "data")
    item = c.inserir_seed("pele", [_img(1), _img(2)])
    c.inserir_scan([_img(3)])
    c.fechar()

    assert (tmp_path / "data" / "catalogo.db").exists()
    c2 = Catalogo(tmp_path / "data")
    itens = c2.listar()
    assert [i.nome for i in itens] == ["pele", "item-000002"]
    reaberto = c2.obter(item.id)
    assert reaberto.origem == "seed"
    assert len(reaberto.imagens) == 2
    assert all(img.caminho.exists() for img in reaberto.imagens)
    v = c2.vetores()
    assert v.matriz.shape == (3, DIMENSAO)
    assert np.allclose(v.matriz[0], _img(1).vetor)
    c2.fechar()


def test_vetores_de_catalogo_vazio(catalogo):
    v = catalogo.vetores()
    assert v.matriz.shape == (0, DIMENSAO)
    assert catalogo.total_itens() == 0


def test_item_sem_imagem_e_recusado(catalogo):
    with pytest.raises(ErroCatalogo):
        catalogo.inserir_scan([])
    assert catalogo.total_itens() == 0


def test_falha_na_insercao_nao_deixa_resto(catalogo):
    ruim = ImagemNova(np.zeros((8, 8, 3), np.uint8), np.zeros(10, np.float32), 1.0)
    with pytest.raises(ErroCatalogo):
        catalogo.inserir_scan([_img(1), ruim])
    assert catalogo.total_itens() == 0
    assert list(catalogo.dir_imagens.iterdir()) == []


# --- 3.2 inserção por scan ---


def test_numeracao_sequencial(catalogo):
    nomes = [catalogo.inserir_scan([_img(i)]).nome for i in range(3)]
    assert nomes == ["item-000001", "item-000002", "item-000003"]


def test_numero_nao_reutilizado_apos_remocao(catalogo):
    for i in range(41):
        catalogo.inserir_scan([_img(i)])
    ultimo = catalogo.inserir_scan([_img(99)])
    assert ultimo.nome == "item-000042"
    catalogo.remover(ultimo.id)
    assert catalogo.inserir_scan([_img(100)]).nome == "item-000043"


def test_insere_os_k_melhores_frames(catalogo):
    frames = []
    for i, p in enumerate([1.0, 5.0, 3.0, 2.0, 4.0]):
        img = _img(i, p)
        frames.append(
            FrameProcessado(Qualidade(1, 100, p, True), True, recorte=img.recorte, vetor=img.vetor)
        )
    scan = Scan(normalizar(np.ones(DIMENSAO)), False, frames, 15, 5)
    item = catalogo.inserir_scan(imagens_do_scan(scan, 3))
    assert item.origem == "scan"
    assert sorted(img.qualidade for img in item.imagens) == [3.0, 4.0, 5.0]
    assert len(list((catalogo.dir_imagens / item.nome).iterdir())) == 3


def test_seed_nao_usa_nome_reservado_nem_repetido(catalogo):
    catalogo.inserir_seed("pele", [_img(1)])
    with pytest.raises(ErroCatalogo):
        catalogo.inserir_seed("pele", [_img(2)])
    with pytest.raises(ErroCatalogo):
        catalogo.inserir_seed("item-000099", [_img(3)])


# --- 3.3 remoção ---


def test_remocao_apaga_banco_disco_e_vetores(catalogo):
    fica = catalogo.inserir_scan([_img(1)])
    sai = catalogo.inserir_scan([_img(2), _img(3)])
    pasta = catalogo.dir_imagens / sai.nome
    assert pasta.exists()

    catalogo.remover(sai.id)

    assert catalogo.obter(sai.id) is None
    assert not pasta.exists()
    v = catalogo.vetores()
    assert set(v.item_ids.tolist()) == {fica.id}
    assert v.matriz.shape == (1, DIMENSAO)


def test_item_de_seed_nao_pode_ser_removido(catalogo):
    seed = catalogo.inserir_seed("lata-coca", [_img(1)])
    with pytest.raises(ErroCatalogo):
        catalogo.remover(seed.id)
    assert catalogo.obter(seed.id) is not None


def test_listar_por_origem(catalogo):
    catalogo.inserir_seed("pele", [_img(1)])
    catalogo.inserir_scan([_img(2)])
    assert [i.nome for i in catalogo.listar("scan")] == ["item-000002"]
    assert [i.nome for i in catalogo.listar("seed")] == ["pele"]
