import numpy as np
import pytest

from scanner.calibracao import Escala, ErroCalibracao, calcular
from scanner.catalogo import Catalogo, ImagemNova
from scanner.embedding import DIMENSAO, normalizar
from scanner.ranking import Decisao, Indice, Resultado, decidir_insercao

ESCALA = Escala(0.0, 0.9)


def _vet(*idx_valor) -> np.ndarray:
    v = np.zeros(DIMENSAO, np.float32)
    for i, x in idx_valor:
        v[i] = x
    return normalizar(v)


def _nova(vetor) -> ImagemNova:
    return ImagemNova(np.zeros((16, 16, 3), np.uint8), vetor, 1.0)


@pytest.fixture
def catalogo(tmp_path):
    c = Catalogo(tmp_path / "data")
    yield c
    c.fechar()


# --- 4.1 índice sincronizado ---


def test_indice_carrega_do_sqlite_e_acompanha_insercao_e_remocao(catalogo):
    a = catalogo.inserir_seed("a", [_nova(_vet((0, 1))), _nova(_vet((1, 1)))])
    indice = Indice.carregar(catalogo)
    assert len(indice) == 2 and indice.total_itens == 1

    vetores = [_vet((2, 1)), _vet((3, 1))]
    b = catalogo.inserir_scan([_nova(v) for v in vetores])
    indice.adicionar(b, np.stack(vetores))
    assert len(indice) == 4 and indice.contem_item(b.id)
    assert indice.buscar(_vet((3, 1)), ESCALA)[0].item_id == b.id

    catalogo.remover(b.id)
    indice.remover(b.id)
    assert len(indice) == 2 and not indice.contem_item(b.id)
    assert all(r.item_id != b.id for r in indice.buscar(_vet((3, 1)), ESCALA))

    recarregado = Indice.carregar(catalogo)
    assert len(recarregado) == len(indice)
    assert recarregado.buscar(_vet((0, 1)), ESCALA)[0].item_id == a.id


def test_adicionar_com_vetores_faltando_falha(catalogo):
    b = catalogo.inserir_scan([_nova(_vet((0, 1))), _nova(_vet((1, 1)))])
    with pytest.raises(ValueError):
        Indice().adicionar(b, _vet((0, 1)))


# --- 4.2 busca por item ---


def _indice_sintetico(n_itens=30, por_item=4, semente=0):
    rng = np.random.default_rng(semente)
    matriz = normalizar(rng.normal(size=(n_itens * por_item, DIMENSAO)))
    item_ids = np.repeat(np.arange(1, n_itens + 1), por_item)
    imagem_ids = np.arange(1, n_itens * por_item + 1)
    caminhos = [f"img{i}.jpg" for i in imagem_ids]
    return Indice(imagem_ids, item_ids, matriz, caminhos), matriz, item_ids, imagem_ids


def test_cada_item_aparece_uma_vez_e_em_ordem():
    indice, matriz, _, _ = _indice_sintetico()
    consulta = normalizar(matriz[0] + matriz[1] + matriz[5])
    res = indice.buscar(consulta, ESCALA, top=10)
    assert len(res) == 10
    ids = [r.item_id for r in res]
    assert len(set(ids)) == 10
    assert all(res[i].cosseno >= res[i + 1].cosseno for i in range(9))
    assert all(res[i].porcentagem >= res[i + 1].porcentagem for i in range(9))


def test_imagem_exibida_e_a_mais_parecida_do_item():
    indice, matriz, item_ids, imagem_ids = _indice_sintetico()
    # A 3ª imagem do item 7 é a consulta exata.
    k = np.flatnonzero(item_ids == 7)[2]
    res = indice.buscar(matriz[k], ESCALA)
    assert res[0].item_id == 7
    assert res[0].imagem_id == imagem_ids[k]
    assert res[0].caminho == f"img{imagem_ids[k]}.jpg"
    assert res[0].porcentagem == pytest.approx(100.0)


def test_catalogo_com_menos_de_10_itens():
    indice, matriz, _, _ = _indice_sintetico(n_itens=4)
    assert len(indice.buscar(matriz[0], ESCALA)) == 4


def test_catalogo_vazio():
    assert Indice().buscar(_vet((0, 1)), ESCALA) == []


def test_ranking_mistura_pessoas_e_objetos_sem_filtro(catalogo):
    pessoa = catalogo.inserir_seed("pessoa", [_nova(_vet((0, 1), (1, 0.2)))])
    objeto = catalogo.inserir_seed("lata", [_nova(_vet((0, 1), (2, 0.1)))])
    indice = Indice.carregar(catalogo)
    res = indice.buscar(_vet((0, 1), (2, 0.1)), ESCALA)
    assert [r.item_id for r in res] == [objeto.id, pessoa.id]


# --- 4.3 porcentagem calibrada ---


def test_escala_nas_ancoras_e_extremos():
    e = Escala(0.3, 0.8)
    assert e(0.3) == pytest.approx(0.0)
    assert e(0.8) == pytest.approx(90.0)
    assert e(1.0) == pytest.approx(100.0)
    assert e(0.55) == pytest.approx(45.0)
    assert e(0.9) == pytest.approx(95.0)
    assert e(-0.5) == 0.0
    assert e(1.2) == 100.0
    assert np.allclose(e(np.array([0.3, 0.8, 1.0])), [0, 90, 100])


def test_escala_rejeita_ancoras_invalidas():
    with pytest.raises(ErroCalibracao):
        Escala(0.8, 0.3)
    with pytest.raises(ErroCalibracao):
        Escala(0.2, 1.0)


def test_calcular_ancoras():
    _, matriz, item_ids, _ = _indice_sintetico(n_itens=10, por_item=3)
    # Aproxima as imagens de cada item para criar pares "iguais" altos.
    centros = normalizar(np.random.default_rng(1).normal(size=(10, DIMENSAO)))
    matriz = normalizar(centros[item_ids - 1] * 3 + matriz)
    r = calcular(item_ids, matriz)
    assert r.escala.cos_zero == pytest.approx(np.median(r.diferentes))
    assert r.escala.cos_noventa == pytest.approx(np.percentile(r.iguais, 10))
    assert r.escala.cos_noventa > r.escala.cos_zero
    assert len(r.iguais) == 10 * 3


def test_calcular_exige_dados_suficientes():
    with pytest.raises(ErroCalibracao):
        calcular(np.array([1, 1]), normalizar(np.eye(2, DIMENSAO)))
    with pytest.raises(ErroCalibracao):
        calcular(np.array([1, 2]), normalizar(np.eye(2, DIMENSAO)))


# --- 4.5 regra de inserção ---


def _res(pct):
    return [Resultado(1, 1, "x.jpg", 0.0, pct)]


@pytest.mark.parametrize(
    "resultados, rosto, esperado",
    [
        (_res(95.0), False, Decisao.DESCARTAR),
        (_res(95.0), True, Decisao.DESCARTAR),
        (_res(90.0), True, Decisao.DESCARTAR),
        (_res(89.99), False, Decisao.INSERIR),
        (_res(72.0), True, Decisao.PEDIR_CONSENTIMENTO),
        ([], False, Decisao.INSERIR),
        ([], True, Decisao.PEDIR_CONSENTIMENTO),
    ],
)
def test_regra_de_insercao(resultados, rosto, esperado):
    assert decidir_insercao(resultados, rosto, 90.0) == esperado


def test_regra_usa_so_o_primeiro_colocado():
    res = [Resultado(1, 1, "a", 0, 50.0), Resultado(2, 2, "b", 0, 95.0)]
    assert decidir_insercao(res, False) == Decisao.INSERIR


# --- 4.4 comando calibrar ---


def test_comando_calibrar_grava_ancoras(tmp_path, capsys):
    from scanner.calibracao import comando_calibrar
    from scanner.config import carregar_config

    config = tmp_path / "config.toml"
    config.write_text("[calibracao]\ncos_zero = 0.5\ncos_noventa = 0.6\n", encoding="utf-8")
    cat = Catalogo(tmp_path / "data")
    rng = np.random.default_rng(3)
    for i in range(5):
        centro = rng.normal(size=DIMENSAO)
        cat.inserir_seed(
            f"item{i}",
            [_nova(normalizar(centro * 3 + rng.normal(size=DIMENSAO))) for _ in range(3)],
        )
    cat.fechar()

    assert comando_calibrar(config) == 0
    saida = capsys.readouterr().out
    assert "Pares do mesmo item (15)" in saida
    assert "Pares de itens diferentes (90)" in saida
    cfg = carregar_config(config)
    assert cfg.calibracao.cos_zero != 0.5
    assert cfg.calibracao.cos_noventa > cfg.calibracao.cos_zero


def test_comando_calibrar_catalogo_insuficiente(tmp_path, capsys):
    from scanner.calibracao import comando_calibrar

    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    assert comando_calibrar(config) == 1
    assert "Não foi possível calibrar" in capsys.readouterr().err
