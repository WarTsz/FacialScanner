from pathlib import Path

from scanner.config import atualizar_calibracao, carregar_config

RAIZ = Path(__file__).resolve().parent.parent


def test_le_valores_do_config_do_projeto():
    cfg = carregar_config(RAIZ / "config.toml")
    assert cfg.captura.n_frames == 15
    assert cfg.captura.min_frames_validos == 5
    assert cfg.catalogo.imagens_por_item == 3
    assert cfg.ranking.limiar_insercao == 90.0
    assert cfg.camera.fonte == 0
    assert cfg.catalogo.diretorio_dados == RAIZ / "data"


def test_chaves_ausentes_assumem_padrao(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text("[captura]\nn_frames = 20\n", encoding="utf-8")
    cfg = carregar_config(arq)
    assert cfg.captura.n_frames == 20
    assert cfg.captura.duracao_s == 5.0
    assert cfg.captura.min_frames_validos == 5
    assert cfg.ranking.top == 10
    assert cfg.modelos.diretorio == tmp_path / "models"


def test_arquivo_ausente_usa_tudo_padrao(tmp_path):
    cfg = carregar_config(tmp_path / "nao-existe.toml")
    assert cfg.captura.n_frames == 15
    assert cfg.catalogo.diretorio_dados == tmp_path / "data"


def test_inteiro_em_campo_float_vira_float(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text("[ranking]\nlimiar_insercao = 85\n", encoding="utf-8")
    assert carregar_config(arq).ranking.limiar_insercao == 85.0


def test_atualizar_calibracao_preserva_resto(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text(
        "# comentario\n[calibracao]\ncos_zero = 0.1\ncos_noventa = 0.5\n\n[ranking]\ntop = 7\n",
        encoding="utf-8",
    )
    atualizar_calibracao(arq, 0.3, 0.8)
    cfg = carregar_config(arq)
    assert cfg.calibracao.cos_zero == 0.3
    assert cfg.calibracao.cos_noventa == 0.8
    assert cfg.ranking.top == 7
    assert "# comentario" in arq.read_text(encoding="utf-8")


def test_atualizar_calibracao_cria_secao(tmp_path):
    arq = tmp_path / "config.toml"
    arq.write_text("[ranking]\ntop = 7\n", encoding="utf-8")
    atualizar_calibracao(arq, 0.2, 0.9)
    cfg = carregar_config(arq)
    assert cfg.calibracao.cos_noventa == 0.9
    assert cfg.ranking.top == 7
