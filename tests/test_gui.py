"""Testes da interface (grupo 5), com pastas de imagens no lugar da webcam."""

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from scanner.captura import ProcessadorFrames
from scanner.catalogo import Catalogo, ImagemNova
from scanner.config import carregar_config
from scanner.embedding import DIMENSAO, normalizar
from scanner.gui.app import MSG_INSERIDO, Estado, JanelaPrincipal
from scanner.gui.tema import aplicar_tema
from scanner.gui.telas import DICA_FALHA
from scanner.motor import Motor
from scanner.ranking import Indice
from tests.conftest import RAIZ, ler, requer_modelos
from tests.seed_exemplo import variacoes

pytestmark = requer_modelos

CAPTURAS = Path("/tmp/claude-1000/-home-wart-Projects-Spec-Trabalho/85561762-8a52-4126-8169-766f0f8a4337/scratchpad/telas")
TIMEOUT = 20_000


@pytest.fixture(scope="module")
def processador():
    return ProcessadorFrames.criar(carregar_config(RAIZ / "config.toml"))


@pytest.fixture
def cfg(tmp_path):
    c = carregar_config(RAIZ / "config.toml")
    c.catalogo.diretorio_dados = tmp_path / "data"
    c.captura.duracao_s = 1.5
    c.captura.n_frames = 8
    return c


def _pasta(tmp_path, nome, imagens):
    pasta = tmp_path / nome
    pasta.mkdir()
    for i, img in enumerate(imagens):
        cv2.imwrite(str(pasta / f"{i}.png"), img)
    return str(pasta)


@pytest.fixture
def fonte_objeto(tmp_path):
    return _pasta(tmp_path, "cam-objeto", variacoes(ler("coffee.png"), 5))


def _astronauta_centralizada() -> np.ndarray:
    """Astronauta deslocada para baixo: o rosto fica dentro da moldura, como o usuário é
    orientado a fazer. Na imagem original o rosto encosta na borda de cima da moldura."""
    img = ler("astronaut.png")
    return cv2.copyMakeBorder(img, 110, 0, 0, 0, cv2.BORDER_REPLICATE)[: img.shape[0]]


@pytest.fixture
def fonte_rosto(tmp_path):
    return _pasta(tmp_path, "cam-rosto", variacoes(_astronauta_centralizada(), 5, semente=7))


@pytest.fixture
def fonte_objeto_com_rosto_ao_lado(tmp_path):
    """Caneca dentro da moldura e um rosto visível fora dela (ex.: quem segura o objeto)."""
    from scanner.recorte import regiao_moldura

    rosto = ler("astronaut.png")[0:340, 60:360]
    caneca = ler("coffee.png")
    frames = []
    for v in variacoes(caneca, 5, semente=3):
        cena = np.full((720, 1280, 3), 120, np.uint8)
        x, y, lado = regiao_moldura(720, 1280, 0.6)
        cena[y : y + lado, x : x + lado] = cv2.resize(v, (lado, lado))
        cena[100:440, 0:300] = rosto
        frames.append(cena)
    return _pasta(tmp_path, "cam-objeto-rosto-fora", frames)


@pytest.fixture(params=["borrada", "coberta"])
def fonte_ruim(request, tmp_path):
    img = ler("rocket.jpg")
    if request.param == "borrada":
        frames = [cv2.GaussianBlur(img, (31, 31), 0)] * 3
    else:  # câmera coberta: frames quase pretos
        frames = [(img * 0.05).astype(np.uint8)] * 3
    return _pasta(tmp_path, f"cam-{request.param}", frames)


@pytest.fixture
def abrir(qtbot, qapp, processador):
    aplicar_tema(qapp)
    janelas = []

    def _abrir(cfg, fonte, esperar_pronto=True, **opcoes):
        def fabrica(c):
            cat = Catalogo(c.catalogo.diretorio_dados)
            return Motor(c, processador, cat, Indice.carregar(cat))

        j = JanelaPrincipal(cfg, fonte, fabrica, **opcoes)
        qtbot.addWidget(j)
        j.show()
        janelas.append(j)
        if esperar_pronto:
            qtbot.waitUntil(lambda: j.tela_camera.botao_escanear.isEnabled(), timeout=TIMEOUT)
        return j

    yield _abrir
    for j in janelas:
        j.close()


def _capturar_tela(janela, nome):
    from PySide6.QtWidgets import QApplication

    for _ in range(3):
        QApplication.processEvents()
    CAPTURAS.mkdir(parents=True, exist_ok=True)
    janela.grab().save(str(CAPTURAS / f"{nome}.png"))


def _escanear(qtbot, j):
    qtbot.mouseClick(j.tela_camera.botao_escanear, Qt.MouseButton.LeftButton)


def _esperar_resultados(qtbot, j):
    qtbot.waitUntil(lambda: j.estado == Estado.RESULTADOS, timeout=TIMEOUT)


def _itens(cfg, origem=None):
    cat = Catalogo(cfg.catalogo.diretorio_dados)
    try:
        return cat.listar(origem)
    finally:
        cat.fechar()


def _foto_dados(cfg) -> dict:
    """Retrato do diretório de dados: arquivos + conteúdo das tabelas."""
    d = cfg.catalogo.diretorio_dados
    arquivos = {
        str(p.relative_to(d)): p.stat().st_size
        for p in d.rglob("*")
        if p.is_file() and p.suffix != ".db" and "journal" not in p.name
    }
    cat = Catalogo(d)
    conteudo = hashlib.sha256(
        repr(cat._con.execute("SELECT * FROM itens").fetchall()).encode()
        + repr(cat._con.execute("SELECT * FROM imagens").fetchall()).encode()
    ).hexdigest()
    cat.fechar()
    return {"arquivos": arquivos, "banco": conteudo}


# --- 5.1 abertura com e sem câmera ---


def test_abre_com_preview_e_botao_escanear(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto)
    qtbot.waitUntil(lambda: not j.tela_camera.preview.pixmap().isNull(), timeout=TIMEOUT)
    assert j.tela_camera.botao_escanear.text() == "Escanear"
    assert j.pilha.currentWidget() is j.tela_camera
    _capturar_tela(j, "1-espera")


def test_sem_camera_desabilita_escanear(qtbot, abrir, cfg):
    j = abrir(cfg, 99, esperar_pronto=False)
    qtbot.waitUntil(lambda: j.motor_pronto, timeout=TIMEOUT)
    qtbot.waitUntil(lambda: not j.camera_ok, timeout=TIMEOUT)
    assert "Câmera não encontrada" in j.tela_camera.mensagem.text()
    assert not j.tela_camera.botao_escanear.isEnabled()
    _capturar_tela(j, "1-sem-camera")


# --- 5.2 captura ---


def test_captura_mostra_moldura_contagem_e_trava_botao(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto)
    _escanear(qtbot, j)
    assert j.estado == Estado.CAPTURANDO
    assert not j.tela_camera.botao_escanear.isEnabled()
    qtbot.wait(400)
    assert j.tela_camera.progresso.isVisible()
    assert j.tela_camera.preview._capturando
    assert "moldura" in j.tela_camera.mensagem.text()
    assert " s" in j.tela_camera.mensagem.text()
    _capturar_tela(j, "2-captura")
    # Interface continua respondendo (o preview segue atualizando).
    antes = j.tela_camera.preview.pixmap().cacheKey()
    qtbot.waitUntil(lambda: j.tela_camera.preview.pixmap().cacheKey() != antes, timeout=2000)
    _esperar_resultados(qtbot, j)


# --- 5.3 falha de captura ---


def test_falha_de_captura_pede_nova_tentativa(qtbot, abrir, cfg, fonte_ruim):
    j = abrir(cfg, fonte_ruim)
    _escanear(qtbot, j)
    qtbot.waitUntil(lambda: j.tela_camera.mensagem.text() == DICA_FALHA, timeout=TIMEOUT)
    assert j.estado == Estado.PRONTO
    assert j.pilha.currentWidget() is j.tela_camera
    assert j.tela_camera.botao_escanear.isEnabled()
    assert _itens(cfg) == []
    _capturar_tela(j, "3-falha")


# --- 5.4 / 5.5 resultados, aviso e consentimento ---


def test_objeto_novo_em_catalogo_vazio_e_inserido_com_aviso(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto)
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    assert j.tela_resultados.vazio.isVisible()
    assert j.dialogo_consentimento is None
    qtbot.waitUntil(lambda: j.tela_resultados.aviso.isVisible(), timeout=TIMEOUT)
    assert j.tela_resultados.aviso.text() == MSG_INSERIDO
    itens = _itens(cfg)
    assert len(itens) == 1 and itens[0].origem == "scan"
    assert len(itens[0].imagens) == cfg.catalogo.imagens_por_item
    # O nome gerado não aparece em lugar nenhum da tela.
    assert all(itens[0].nome not in l.text() for l in j.findChildren(QLabel))
    _capturar_tela(j, "4-objeto-inserido")


def test_objeto_na_moldura_com_rosto_fora_e_escaneado_como_objeto(
    qtbot, abrir, cfg, fonte_objeto_com_rosto_ao_lado
):
    j = abrir(cfg, fonte_objeto_com_rosto_ao_lado)
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    assert not j.resultado_atual.scan.contem_rosto
    assert j.dialogo_consentimento is None  # objeto: sem pedido de consentimento
    qtbot.waitUntil(lambda: len(_itens(cfg, "scan")) == 1, timeout=TIMEOUT)


def test_amostragem_nao_repete_o_mesmo_frame(qtbot, abrir, cfg, fonte_objeto):
    """Se a câmera não entregou frame novo, a amostra espera o próximo em vez de repetir."""
    from scanner.gui.camera import para_qimage

    j = abrir(cfg, fonte_objeto)
    enviados = []
    j._pedir_processar.connect(lambda f: enviados.append(f))
    frame = np.full((480, 640, 3), 90, np.uint8)
    atual = [(7, frame)]
    j.camera.ultimo_frame_numerado = lambda: atual[0]
    j.estado = Estado.CAPTURANDO
    j._seq_amostrado, j._amostras_pendentes = -1, 0
    try:
        j._amostrar()
        j._amostrar()  # mesmo frame 7: não reenvia, fica pendente
        assert len(enviados) == 1 and j._amostras_pendentes == 1
        atual[0] = (8, frame.copy())
        j._frame(para_qimage(frame))  # chega o frame 8
        assert len(enviados) == 2 and j._amostras_pendentes == 0
    finally:
        j.estado = Estado.PRONTO


def test_scan_repetido_e_descartado_e_ranking_sem_nomes(qtbot, abrir, cfg, fonte_objeto):
    cat = Catalogo(cfg.catalogo.diretorio_dados)
    rng = np.random.default_rng(0)
    for i in range(12):
        cat.inserir_seed(
            f"seed{i}",
            [ImagemNova(ler("chelsea.png")[:64, :64], normalizar(rng.normal(size=DIMENSAO)), 1.0)],
        )
    cat.fechar()
    j = abrir(cfg, fonte_objeto)
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    qtbot.waitUntil(lambda: len(_itens(cfg, "scan")) == 1, timeout=TIMEOUT)

    qtbot.mouseClick(j.tela_resultados.botao_novo, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is j.tela_camera
    qtbot.waitUntil(lambda: j.tela_camera.botao_escanear.isEnabled(), timeout=TIMEOUT)
    foto = _foto_dados(cfg)
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    qtbot.wait(500)

    cartoes = j.tela_resultados.cartoes()
    assert len(cartoes) == 10
    assert cartoes[0].porcentagem >= 90
    assert all(cartoes[i].porcentagem >= cartoes[i + 1].porcentagem for i in range(9))
    textos = " ".join(l.text() for l in j.findChildren(QLabel))
    assert "item-" not in textos and "seed" not in textos
    assert not j.tela_resultados.aviso.isVisible()
    assert j.dialogo_consentimento is None
    assert len(_itens(cfg, "scan")) == 1
    assert _foto_dados(cfg) == foto  # 5.7: scan descartado não toca o disco
    _capturar_tela(j, "4-resultados")


def test_rosto_com_consentimento_aceito(qtbot, abrir, cfg, fonte_rosto):
    j = abrir(cfg, fonte_rosto)
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    qtbot.waitUntil(lambda: j.dialogo_consentimento is not None, timeout=TIMEOUT)
    texto = j.dialogo_consentimento.findChild(QLabel).text()
    assert "armazenadas" in texto and "outras pessoas" in texto
    _capturar_tela(j.dialogo_consentimento, "5-consentimento")
    qtbot.mouseClick(j.dialogo_consentimento.botao_ok, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: j.tela_resultados.aviso.isVisible(), timeout=TIMEOUT)
    assert j.tela_resultados.aviso.text() == MSG_INSERIDO
    assert len(_itens(cfg, "scan")) == 1


def test_rosto_com_consentimento_recusado_nao_grava_nada(qtbot, abrir, cfg, fonte_rosto):
    j = abrir(cfg, fonte_rosto)
    foto = _foto_dados(cfg)
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    qtbot.waitUntil(lambda: j.dialogo_consentimento is not None, timeout=TIMEOUT)
    qtbot.mouseClick(j.dialogo_consentimento.botao_cancelar, Qt.MouseButton.LeftButton)
    qtbot.wait(500)
    assert j.dialogo_consentimento is None
    assert j.pilha.currentWidget() is j.tela_resultados  # ranking continua visível
    assert not j.tela_resultados.aviso.isVisible()
    assert _itens(cfg) == []
    assert _foto_dados(cfg) == foto  # 5.7


# --- 5.6 remoção ---


def _popular_para_remocao(cfg):
    cat = Catalogo(cfg.catalogo.diretorio_dados)
    rng = np.random.default_rng(1)
    img = lambda: ImagemNova(ler("coffee.png")[:128, :128], normalizar(rng.normal(size=DIMENSAO)), 1.0)
    cat.inserir_seed("pessoa-publica", [img()])
    a = cat.inserir_scan([img()])
    b = cat.inserir_scan([img(), img()])
    cat.fechar()
    return a, b


def _abrir_remocao(qtbot, j):
    qtbot.mouseClick(j.tela_camera.botao_gerenciar, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is j.tela_remocao


def _selecionar(j, nome):
    lista = j.tela_remocao.lista
    item = next(lista.item(i) for i in range(lista.count()) if lista.item(i).text() == nome)
    lista.setCurrentItem(item)


def test_remocao_confirmada(qtbot, abrir, cfg, fonte_objeto):
    a, b = _popular_para_remocao(cfg)
    j = abrir(cfg, fonte_objeto)
    _abrir_remocao(qtbot, j)
    lista = j.tela_remocao.lista
    assert sorted(lista.item(i).text() for i in range(lista.count())) == [a.nome, b.nome]
    assert not j.tela_remocao.botao_remover.isEnabled()

    _selecionar(j, b.nome)
    _capturar_tela(j, "6-remocao")
    qtbot.mouseClick(j.tela_remocao.botao_remover, Qt.MouseButton.LeftButton)
    dialogo = j.tela_remocao.confirmacao
    assert dialogo.isVisible()
    qtbot.mouseClick(dialogo.botao_ok, Qt.MouseButton.LeftButton)

    assert [lista.item(i).text() for i in range(lista.count())] == [a.nome]
    assert [i.nome for i in _itens(cfg, "scan")] == [a.nome]
    assert not (cfg.catalogo.diretorio_dados / "images" / b.nome).exists()
    assert not j.trabalhador.motor.indice.contem_item(b.id)
    assert [i.nome for i in _itens(cfg, "seed")] == ["pessoa-publica"]


def test_remocao_cancelada(qtbot, abrir, cfg, fonte_objeto):
    a, b = _popular_para_remocao(cfg)
    j = abrir(cfg, fonte_objeto)
    _abrir_remocao(qtbot, j)
    _selecionar(j, a.nome)
    qtbot.mouseClick(j.tela_remocao.botao_remover, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(j.tela_remocao.confirmacao.botao_cancelar, Qt.MouseButton.LeftButton)
    assert j.tela_remocao.lista.count() == 2
    assert len(_itens(cfg, "scan")) == 2
    qtbot.mouseClick(j.tela_remocao.botao_voltar, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is j.tela_camera


def test_remocao_sem_itens_de_scan(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto)
    _abrir_remocao(qtbot, j)
    assert j.tela_remocao.vazio.isVisible()
    assert j.tela_remocao.lista.count() == 0


# --- 7.2 adição manual de imagens ---


def _arquivos(tmp_path, nome, imagens):
    pasta = Path(_pasta(tmp_path, nome, imagens))
    return sorted(str(p) for p in pasta.iterdir())


def _adicionar(qtbot, j, caminhos):
    j._escolher_arquivos = lambda: caminhos  # no lugar do QFileDialog
    qtbot.mouseClick(j.tela_camera.botao_adicionar, Qt.MouseButton.LeftButton)


def test_adicionar_imagens_cria_item_com_aviso(qtbot, abrir, cfg, tmp_path):
    j = abrir(cfg, _pasta(tmp_path, "cam", variacoes(ler("coffee.png"), 2)))
    caminhos = _arquivos(tmp_path, "escolhidas", variacoes(ler("chelsea.png"), 3, semente=2))
    borrada = _arquivos(tmp_path, "ruins", [cv2.GaussianBlur(ler("rocket.jpg"), (31, 31), 0)])
    _adicionar(qtbot, j, caminhos + borrada)
    assert j.estado == Estado.ADICIONANDO
    assert not j.tela_camera.botao_escanear.isEnabled()
    assert not j.tela_camera.botao_adicionar.isEnabled()
    qtbot.waitUntil(lambda: j.estado == Estado.PRONTO, timeout=TIMEOUT)
    texto = j.tela_camera.mensagem.text()
    assert f"{MSG_INSERIDO} com 3 imagens." in texto
    assert "Ignorada: 0.png (borrado)." in texto
    itens = _itens(cfg, "scan")
    assert len(itens) == 1 and len(itens[0].imagens) == 3
    assert itens[0].nome not in texto  # o nome gerado não aparece
    assert j.dialogo_consentimento is None
    assert j.tela_camera.botao_adicionar.isEnabled()
    assert "1 item no catálogo" in j.status_itens.text()
    _capturar_tela(j, "8-imagens-adicionadas")


def test_adicionar_sem_imagens_validas_nao_grava(qtbot, abrir, cfg, tmp_path):
    j = abrir(cfg, _pasta(tmp_path, "cam", variacoes(ler("coffee.png"), 2)))
    _adicionar(qtbot, j, _arquivos(tmp_path, "ruins", [(ler("rocket.jpg") * 0.05).astype(np.uint8)]))
    qtbot.waitUntil(lambda: j.estado == Estado.PRONTO, timeout=TIMEOUT)
    assert "nada foi adicionado" in j.tela_camera.mensagem.text()
    assert "escuro demais" in j.tela_camera.mensagem.text()
    assert j.tela_camera.mensagem.property("erro")
    assert _itens(cfg) == []


def test_adicionar_com_seletor_cancelado_nao_faz_nada(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto)
    antes = j.tela_camera.mensagem.text()
    _adicionar(qtbot, j, [])
    qtbot.wait(200)
    assert j.estado == Estado.PRONTO
    assert j.tela_camera.mensagem.text() == antes
    assert _itens(cfg) == []


def test_adicionar_imagens_disponivel_sem_camera(qtbot, abrir, cfg, tmp_path):
    j = abrir(cfg, 99, esperar_pronto=False)
    qtbot.waitUntil(lambda: j.motor_pronto and not j.camera_ok, timeout=TIMEOUT)
    assert not j.tela_camera.botao_escanear.isEnabled()
    assert j.tela_camera.botao_adicionar.isEnabled()
    _adicionar(qtbot, j, _arquivos(tmp_path, "escolhidas", [ler("coffee.png")]))
    qtbot.waitUntil(lambda: j.estado == Estado.PRONTO, timeout=TIMEOUT)
    assert len(_itens(cfg, "scan")) == 1
    assert not j.tela_camera.botao_escanear.isEnabled()  # continua sem câmera


# --- ícone do aplicativo ---


def test_icone_do_aplicativo(qtbot, abrir, cfg, fonte_objeto):
    from scanner.gui.tema import TAMANHOS_ICONE, icone_app

    icone = icone_app()
    assert not icone.isNull()
    tamanhos = {s.width() for s in icone.availableSizes()}
    assert set(TAMANHOS_ICONE) <= tamanhos
    j = abrir(cfg, fonte_objeto)
    assert not j.windowIcon().isNull()
    assert {s.width() for s in j.windowIcon().availableSizes()} >= {16, 256}


# --- 8.3 comparação de imagens com o catálogo ---


def _imagens_comparacao(tmp_path):
    from tests.seed_exemplo import sequencia_camera

    canecas = _arquivos(tmp_path, "cmp-caneca", sequencia_camera(ler("coffee.png"), 3, semente=1))
    foguete = _arquivos(tmp_path, "cmp-foguete", [ler("rocket.jpg")])
    borrada = _arquivos(tmp_path, "cmp-borrada", [cv2.GaussianBlur(ler("coffee.png"), (31, 31), 0)])
    return canecas, foguete[0], borrada[0]


def _abrir_comparacao(qtbot, j, caminhos=None):
    if caminhos is not None:
        j._escolher_arquivos_comparacao = lambda: caminhos  # no lugar do QFileDialog
    qtbot.mouseClick(j.tela_camera.botao_comparar, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is j.tela_comparacao
    assert j.estado == Estado.COMPARACAO


def _soltar(area, caminhos):
    from PySide6.QtCore import QMimeData, QPointF, QUrl
    from PySide6.QtGui import QDropEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(c)) for c in caminhos])
    evento = QDropEvent(
        QPointF(20, 20), Qt.DropAction.CopyAction, mime, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
    )
    area.dropEvent(evento)


def test_comparar_imagens_disponivel_sem_camera(qtbot, abrir, cfg):
    j = abrir(cfg, 99, esperar_pronto=False)
    qtbot.waitUntil(lambda: j.motor_pronto and not j.camera_ok, timeout=TIMEOUT)
    assert not j.tela_camera.botao_escanear.isEnabled()
    assert j.tela_camera.botao_comparar.isEnabled()
    _abrir_comparacao(qtbot, j)


def test_arrastar_imagens_e_habilitar_comparar(qtbot, abrir, cfg, fonte_objeto, tmp_path):
    canecas, foguete, _ = _imagens_comparacao(tmp_path)
    texto = tmp_path / "notas.txt"
    texto.write_text("x")
    j = abrir(cfg, fonte_objeto)
    _abrir_comparacao(qtbot, j, [str(foguete)])
    tela = j.tela_comparacao
    assert not tela.botao_comparar.isEnabled()

    _soltar(tela.area, [*canecas[:2], texto])
    assert tela.area.miniaturas.count() == 2
    assert "1 arquivo ignorado" in tela.mensagem.text()
    assert tela.botao_comparar.isEnabled()

    qtbot.mouseClick(tela.botao_escolher, Qt.MouseButton.LeftButton)  # acrescenta
    assert tela.area.miniaturas.count() == 3
    _soltar(tela.area, canecas[:1])  # repetida não entra de novo
    assert tela.area.miniaturas.count() == 3
    _capturar_tela(j, "9-comparacao")

    qtbot.mouseClick(tela.botao_limpar, Qt.MouseButton.LeftButton)
    assert tela.area.miniaturas.count() == 0 and not tela.botao_comparar.isEnabled()


def test_comparar_mostra_ranking_com_resumo_e_insere(qtbot, abrir, cfg, fonte_objeto, tmp_path):
    canecas, foguete, borrada = _imagens_comparacao(tmp_path)
    j = abrir(cfg, fonte_objeto)
    _abrir_comparacao(qtbot, j)
    tela = j.tela_comparacao
    _soltar(tela.area, [canecas[0], foguete, borrada, canecas[1], canecas[2]])
    qtbot.mouseClick(tela.botao_comparar, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: j.estado == Estado.RESULTADOS, timeout=TIMEOUT)

    res = j.tela_resultados
    assert j.pilha.currentWidget() is res
    assert res.botao_novo.text() == "Nova comparação"
    resumo = res.resumo.text()
    assert "Usadas:</b> 3 imagens" in resumo
    assert "Descartadas por qualidade:</b> 0.png (borrado)" in resumo
    assert "Diferentes do grupo escolhido:</b> 0.png" in resumo
    assert res.aviso.isVisible() and res.aviso.text() == MSG_INSERIDO  # catálogo vazio: vira item
    itens = _itens(cfg, "scan")
    assert len(itens) == 1 and len(itens[0].imagens) == 3
    _capturar_tela(j, "10-comparacao-resultado")

    # Nova comparação: volta para a tela de comparação, limpa.
    qtbot.mouseClick(res.botao_novo, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is tela and tela.area.miniaturas.count() == 0

    # As mesmas imagens de novo: já catalogadas (>= 90%), nada é gravado.
    foto = _foto_dados(cfg)
    _soltar(tela.area, canecas)
    qtbot.mouseClick(tela.botao_comparar, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: j.estado == Estado.RESULTADOS, timeout=TIMEOUT)
    assert res.cartoes()[0].porcentagem >= 90
    assert not res.aviso.isVisible()
    assert _foto_dados(cfg) == foto

    # Depois de um scan, o botão volta a ser "Novo scan".
    qtbot.mouseClick(res.botao_novo, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(tela.botao_voltar, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is j.tela_camera and j.estado == Estado.PRONTO
    _escanear(qtbot, j)
    _esperar_resultados(qtbot, j)
    assert res.botao_novo.text() == "Novo scan" and not res.resumo.isVisible()


def test_comparar_sem_imagem_valida_continua_na_tela(qtbot, abrir, cfg, fonte_objeto, tmp_path):
    escura = _arquivos(tmp_path, "cmp-escura", [(ler("rocket.jpg") * 0.05).astype(np.uint8)])
    j = abrir(cfg, fonte_objeto)
    _abrir_comparacao(qtbot, j)
    _soltar(j.tela_comparacao.area, escura)
    qtbot.mouseClick(j.tela_comparacao.botao_comparar, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: j.tela_comparacao.mensagem.isVisible(), timeout=TIMEOUT)
    assert j.pilha.currentWidget() is j.tela_comparacao and j.estado == Estado.COMPARACAO
    texto = j.tela_comparacao.mensagem.text()
    assert "Nenhuma imagem válida" in texto and "escuro demais" in texto
    assert _itens(cfg) == []
    qtbot.mouseClick(j.tela_comparacao.botao_voltar, Qt.MouseButton.LeftButton)
    assert j.pilha.currentWidget() is j.tela_camera and j.estado == Estado.PRONTO


# --- 9.2 câmera opcional e dispositivos ---


def _botoes_sem_camera_ok(j):
    t = j.tela_camera
    return (
        not t.botao_escanear.isEnabled()
        and t.botao_adicionar.isEnabled()
        and t.botao_comparar.isEnabled()
        and t.botao_gerenciar.isEnabled()
    )


def test_desativar_e_ativar_a_camera(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto, listar=lambda: [])
    t = j.tela_camera
    assert t.botao_camera.text() == "Desativar" and j.camera is not None

    qtbot.mouseClick(t.botao_camera, Qt.MouseButton.LeftButton)
    assert j.camera is None and not j.camera_ativa
    assert t.preview.text() == "Câmera desativada"
    assert t.botao_camera.text() == "Ativar"
    assert _botoes_sem_camera_ok(j)
    _capturar_tela(j, "11-camera-desativada")

    qtbot.mouseClick(t.botao_camera, Qt.MouseButton.LeftButton)
    assert j.camera is not None and j.camera_ativa
    qtbot.waitUntil(lambda: t.preview.pixmap() is not None and not t.preview.pixmap().isNull(), timeout=TIMEOUT)
    qtbot.waitUntil(lambda: t.botao_escanear.isEnabled(), timeout=TIMEOUT)


def test_trocar_de_dispositivo(qtbot, abrir, cfg, fonte_objeto, fonte_rosto):
    from scanner.dispositivos import Dispositivo

    lista = [Dispositivo(fonte_objeto, "Câmera A"), Dispositivo(fonte_rosto, "Câmera B")]
    j = abrir(cfg, fonte_objeto, listar=lambda: lista)
    t = j.tela_camera
    assert [t.lista_cameras.itemText(i) for i in range(t.lista_cameras.count())] == ["Câmera A", "Câmera B"]
    antiga = j.camera
    t.lista_cameras.activated.emit(1)
    assert j.fonte_atual == fonte_rosto and j.camera is not antiga
    assert t.lista_cameras.currentIndex() == 1
    qtbot.waitUntil(lambda: j.camera.ultimo_frame() is not None, timeout=TIMEOUT)
    assert np.array_equal(j.camera.ultimo_frame(), cv2.imread(str(sorted(Path(fonte_rosto).iterdir())[0])))


def test_dispositivo_que_nao_abre_desativa_a_camera(qtbot, abrir, cfg, fonte_objeto):
    from scanner.dispositivos import Dispositivo

    lista = [Dispositivo(fonte_objeto, "Câmera A"), Dispositivo(98, "Fantasma")]
    j = abrir(cfg, fonte_objeto, listar=lambda: lista)
    j.tela_camera.lista_cameras.activated.emit(1)
    qtbot.waitUntil(lambda: not j.camera_ativa, timeout=TIMEOUT)
    t = j.tela_camera
    assert j.camera is None and t.botao_camera.text() == "Ativar"
    assert t.mensagem.text().startswith("Câmera não encontrada")
    assert _botoes_sem_camera_ok(j)


def test_nenhum_dispositivo(qtbot, abrir, cfg):
    j = abrir(cfg, 97, esperar_pronto=False, listar=lambda: [])
    qtbot.waitUntil(lambda: j.motor_pronto, timeout=TIMEOUT)
    t = j.tela_camera
    assert t.lista_cameras.itemText(0) == "Nenhuma câmera encontrada"
    assert not t.lista_cameras.isEnabled() and not t.botao_camera.isEnabled()
    assert t.botao_atualizar.isEnabled()
    assert _botoes_sem_camera_ok(j)


def test_atualizar_lista_encontra_camera_nova(qtbot, abrir, cfg, fonte_objeto):
    from scanner.dispositivos import Dispositivo

    conectadas = []
    j = abrir(cfg, 97, esperar_pronto=False, listar=lambda: list(conectadas))
    qtbot.waitUntil(lambda: j.motor_pronto, timeout=TIMEOUT)
    conectadas.append(Dispositivo(fonte_objeto, "Webcam nova"))
    qtbot.mouseClick(j.tela_camera.botao_atualizar, Qt.MouseButton.LeftButton)
    t = j.tela_camera
    assert t.lista_cameras.itemText(0) == "Webcam nova" and t.botao_camera.isEnabled()
    assert "1 câmera encontrada" in t.mensagem.text()
    qtbot.mouseClick(t.botao_camera, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: t.botao_escanear.isEnabled(), timeout=TIMEOUT)


def test_controles_de_camera_travados_durante_o_scan(qtbot, abrir, cfg, fonte_objeto):
    j = abrir(cfg, fonte_objeto, listar=lambda: [])
    t = j.tela_camera
    _escanear(qtbot, j)
    assert not t.lista_cameras.isEnabled() and not t.botao_camera.isEnabled()
    assert not t.botao_atualizar.isEnabled()
    _esperar_resultados(qtbot, j)
    qtbot.mouseClick(j.tela_resultados.botao_novo, Qt.MouseButton.LeftButton)
    assert t.botao_camera.isEnabled() and t.botao_atualizar.isEnabled()


def test_lembra_a_ultima_escolha(qtbot, abrir, cfg, tmp_path):
    from scanner.config import carregar_config
    from scanner.dispositivos import Dispositivo

    arquivo = tmp_path / "config.toml"
    arquivo.write_text("[camera]\nfonte = 5\nativa = false\n", encoding="utf-8")
    cfg.caminho = arquivo
    cfg.camera.fonte, cfg.camera.ativa = 5, False
    lista = [Dispositivo(5, "Câmera A"), Dispositivo(6, "Câmera B")]

    # Câmera desativada: trocar de dispositivo não abre nenhum, só grava a escolha.
    j = abrir(cfg, 5, esperar_pronto=False, listar=lambda: lista, salvar_camera=True)
    qtbot.waitUntil(lambda: j.motor_pronto, timeout=TIMEOUT)
    assert j.camera is None and j.tela_camera.preview.text() == "Câmera desativada"
    j.tela_camera.lista_cameras.activated.emit(1)
    assert j.camera is None
    salvo = carregar_config(arquivo).camera
    assert (salvo.fonte, salvo.ativa) == (6, False)
    j.close()

    # Reabrir: a mesma escolha, ainda desativada.
    novo = carregar_config(arquivo)
    novo.catalogo.diretorio_dados = cfg.catalogo.diretorio_dados
    j2 = abrir(novo, novo.camera.fonte, esperar_pronto=False, listar=lambda: lista, salvar_camera=True)
    qtbot.waitUntil(lambda: j2.motor_pronto, timeout=TIMEOUT)
    assert j2.tela_camera.lista_cameras.currentText() == "Câmera B (câmera 6)"
    assert j2.camera is None and j2.tela_camera.preview.text() == "Câmera desativada"
    assert _botoes_sem_camera_ok(j2)


def test_dispositivo_guardado_ausente_abre_desativada(qtbot, abrir, cfg):
    from scanner.dispositivos import Dispositivo

    cfg.camera.ativa = True
    j = abrir(cfg, 7, esperar_pronto=False, listar=lambda: [Dispositivo(5, "Câmera A")])
    qtbot.waitUntil(lambda: j.motor_pronto, timeout=TIMEOUT)
    assert j.camera is None and not j.camera_ativa
    assert j.tela_camera.mensagem.text().startswith("Câmera não encontrada")
    assert j.tela_camera.botao_camera.text() == "Ativar"


def test_testes_nao_gravam_no_config_do_projeto(qtbot, abrir, cfg, fonte_objeto):
    antes = (RAIZ / "config.toml").read_text(encoding="utf-8")
    j = abrir(cfg, fonte_objeto, listar=lambda: [])
    qtbot.mouseClick(j.tela_camera.botao_camera, Qt.MouseButton.LeftButton)
    assert (RAIZ / "config.toml").read_text(encoding="utf-8") == antes
