"""Telas do aplicativo: câmera, resultados, remoção e diálogo de consentimento."""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
    QComboBox,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from scanner.gui.tema import CORES
from scanner.recorte import regiao_moldura

TEXTO_CONSENTIMENTO = (
    f"<p style='font-size:17px; font-weight:700; color:{CORES['branco']}'>"
    "Adicionar seu rosto ao catálogo?</p>"
    "<p>Este scan é diferente de todos os itens do catálogo. Se você aceitar, "
    f"<b style='color:{CORES['rosa']}'>imagens do seu rosto serão armazenadas neste computador</b> e "
    f"<b style='color:{CORES['rosa']}'>poderão aparecer nos resultados de outras pessoas</b> "
    "que usarem o scanner.</p>"
    f"<p style='color:{CORES['texto_mudo']}'>O item pode ser removido a qualquer momento em "
    "<i>Gerenciar itens</i>. Se você recusar, nada é guardado.</p>"
)
DICA_FALHA = (
    "Tente novamente: não foi possível obter imagens nítidas suficientes.\n"
    "Dica: fique em um lugar bem iluminado, centralize o rosto ou o objeto na "
    "moldura e evite se mexer durante os 5 segundos."
)


def _cabecalho(titulo: str, subtitulo: str) -> QVBoxLayout:
    t = QLabel(titulo)
    t.setObjectName("titulo")
    s = QLabel(subtitulo)
    s.setObjectName("subtitulo")
    s.setWordWrap(True)
    caixa = QVBoxLayout()
    caixa.setSpacing(2)
    caixa.addWidget(t)
    caixa.addWidget(s)
    return caixa


def pixmap_arredondado(caminho, lado: int, raio: int = 10) -> QPixmap:
    origem = QPixmap(str(caminho))
    destino = QPixmap(lado, lado)
    destino.fill(Qt.GlobalColor.transparent)
    if origem.isNull():
        return destino
    origem = origem.scaled(
        lado,
        lado,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    pintor = QPainter(destino)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    caminho_clip = QPainterPath()
    caminho_clip.addRoundedRect(QRectF(0, 0, lado, lado), raio, raio)
    pintor.setClipPath(caminho_clip)
    pintor.drawPixmap((lado - origem.width()) // 2, (lado - origem.height()) // 2, origem)
    pintor.end()
    return destino


class Preview(QLabel):
    """Frame da câmera (espelhado) com área externa escurecida e cantos de scanner."""

    def __init__(self, fracao_moldura: float, parent=None):
        super().__init__(parent)
        self._fracao = fracao_moldura
        self._capturando = False
        self._progresso = 0.0
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName("preview")

    def set_capturando(self, valor: bool) -> None:
        self._capturando = valor
        if not valor:
            self._progresso = 0.0
        self._redesenhar()

    def set_progresso(self, fracao: float) -> None:
        self._progresso = min(max(fracao, 0.0), 1.0)

    def clear(self) -> None:
        self._ultimo = None
        super().clear()

    def _redesenhar(self) -> None:
        if getattr(self, "_ultimo", None) is not None:
            self.mostrar(self._ultimo)

    def mostrar(self, img: QImage) -> None:
        self._ultimo = img
        if hasattr(img, "flipped"):  # Qt >= 6.9
            img = img.flipped(Qt.Orientation.Horizontal)
        else:
            img = img.mirrored(True, False)
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        w, h = img.width(), img.height()
        x, y, lado = regiao_moldura(h, w, self._fracao)
        raio = lado * 0.06
        espessura = max(3, w // 140)

        pintor = QPainter(img)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Escurece tudo fora da moldura.
        fora = QPainterPath()
        fora.addRect(QRectF(0, 0, w, h))
        furo = QPainterPath()
        furo.addRoundedRect(QRectF(x, y, lado, lado), raio, raio)
        pintor.fillPath(fora.subtracted(furo), QColor(10, 10, 14, 120))

        # Cantos da moldura: brancos parados, rosa durante a captura.
        cor = QColor(CORES["rosa"] if self._capturando else CORES["branco"])
        pintor.setPen(QPen(cor, espessura, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        c = lado * 0.16
        for cx, cy, dx, dy in (
            (x, y, 1, 1),
            (x + lado, y, -1, 1),
            (x, y + lado, 1, -1),
            (x + lado, y + lado, -1, -1),
        ):
            pintor.drawLine(int(cx), int(cy + dy * raio), int(cx), int(cy + dy * c))
            pintor.drawLine(int(cx + dx * raio), int(cy), int(cx + dx * c), int(cy))
            pintor.drawArc(
                QRectF(cx if dx > 0 else cx - 2 * raio, cy if dy > 0 else cy - 2 * raio, 2 * raio, 2 * raio),
                {(1, 1): 90, (-1, 1): 0, (1, -1): 180, (-1, -1): 270}[(dx, dy)] * 16,
                90 * 16,
            )

        # Linha de varredura ciano durante a captura.
        if self._capturando:
            ly = y + lado * self._progresso
            brilho = lado * 0.08
            grad = QLinearGradient(0, ly - brilho, 0, ly)
            ciano = QColor(CORES["ciano"])
            transparente = QColor(ciano)
            transparente.setAlpha(0)
            meio = QColor(ciano)
            meio.setAlpha(70)
            grad.setColorAt(0, transparente)
            grad.setColorAt(1, meio)
            pintor.fillRect(QRectF(x + 2, ly - brilho, lado - 4, brilho), grad)
            pintor.setPen(QPen(ciano, max(2, espessura // 2)))
            pintor.drawLine(int(x + raio / 2), int(ly), int(x + lado - raio / 2), int(ly))
        pintor.end()

        self.setPixmap(
            QPixmap.fromImage(img).scaled(
                self.size() - QSize(4, 4),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class TelaCamera(QWidget):
    escanear = Signal()
    gerenciar = Signal()
    adicionar = Signal()
    comparar = Signal()
    camera_escolhida = Signal(int)  # posição na lista de dispositivos
    alternar_camera = Signal()
    atualizar_cameras = Signal()

    def __init__(self, fracao_moldura: float, parent=None):
        super().__init__(parent)
        # Barra de câmera: dispositivo, ativar/desativar e atualizar lista.
        rotulo_camera = QLabel("Câmera")
        rotulo_camera.setObjectName("subtitulo")
        self.lista_cameras = QComboBox()
        self.lista_cameras.setMinimumWidth(260)
        self.lista_cameras.activated.connect(self.camera_escolhida)
        self.botao_camera = QPushButton("Desativar")
        self.botao_camera.setObjectName("alternarCamera")
        self.botao_camera.clicked.connect(self.alternar_camera)
        self.botao_atualizar = QPushButton("Atualizar lista")
        self.botao_atualizar.setToolTip("Procura de novo as câmeras conectadas")
        self.botao_atualizar.clicked.connect(self.atualizar_cameras)
        barra_camera = QHBoxLayout()
        barra_camera.addWidget(rotulo_camera)
        barra_camera.addWidget(self.lista_cameras)
        barra_camera.addWidget(self.botao_camera)
        barra_camera.addWidget(self.botao_atualizar)
        barra_camera.addStretch()
        self.preview = Preview(fracao_moldura)
        self.mensagem = QLabel("Carregando modelos…")
        self.mensagem.setObjectName("mensagem")
        self.mensagem.setWordWrap(True)
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progresso = QProgressBar()
        self.progresso.setTextVisible(False)
        self.progresso.hide()
        self.botao_escanear = QPushButton("Escanear")
        self.botao_escanear.setObjectName("primario")
        self.botao_escanear.setMinimumWidth(160)
        self.botao_escanear.setEnabled(False)
        self.botao_escanear.clicked.connect(self.escanear)
        self.botao_gerenciar = QPushButton("Gerenciar itens")
        self.botao_gerenciar.setEnabled(False)
        self.botao_gerenciar.clicked.connect(self.gerenciar)
        self.botao_adicionar = QPushButton("Adicionar imagens")
        self.botao_adicionar.setToolTip(
            "Escolha uma ou mais imagens do mesmo rosto ou objeto para criar um novo item"
        )
        self.botao_adicionar.setEnabled(False)
        self.botao_adicionar.clicked.connect(self.adicionar)
        self.botao_comparar = QPushButton("Comparar imagens")
        self.botao_comparar.setToolTip(
            "Compare dois objetos a partir de arquivos de imagem, sem usar a câmera"
        )
        self.botao_comparar.setEnabled(False)
        self.botao_comparar.clicked.connect(self.comparar)

        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_gerenciar)
        botoes.addWidget(self.botao_adicionar)
        botoes.addWidget(self.botao_comparar)
        botoes.addStretch()
        botoes.addWidget(self.botao_escanear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addLayout(barra_camera)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.mensagem)
        layout.addWidget(self.progresso)
        layout.addLayout(botoes)

    def info(self, texto: str, erro: bool = False) -> None:
        self.mensagem.setText(texto)
        self.mensagem.setProperty("erro", erro)
        self.mensagem.style().unpolish(self.mensagem)
        self.mensagem.style().polish(self.mensagem)

    def sem_camera(self, motivo: str) -> None:
        self.preview.clear()
        self.preview.setText("Câmera não encontrada")
        self.info(
            "Câmera não encontrada. Conecte uma câmera e clique em “Atualizar lista”, ou continue "
            f"sem câmera: adicionar, comparar e gerenciar funcionam normalmente.\n({motivo})",
            True,
        )

    def camera_desativada(self) -> None:
        self.preview.clear()
        self.preview.setText("Câmera desativada")
        self.info(
            "Câmera desativada. Adicionar imagens, comparar imagens e gerenciar itens "
            "continuam disponíveis."
        )

    def mostrar_dispositivos(self, dispositivos, atual, ativa: bool) -> None:
        """Preenche a lista, seleciona `atual` (fonte) e ajusta o botão Ativar/Desativar."""
        self.lista_cameras.blockSignals(True)
        self.lista_cameras.clear()
        if dispositivos:
            for d in dispositivos:
                self.lista_cameras.addItem(d.rotulo, d.fonte)
            fontes = [d.fonte for d in dispositivos]
            self.lista_cameras.setCurrentIndex(fontes.index(atual) if atual in fontes else 0)
        else:
            self.lista_cameras.addItem("Nenhuma câmera encontrada")
        self.lista_cameras.blockSignals(False)
        self.botao_camera.setText("Desativar" if ativa else "Ativar")

    def progresso_captura(self, decorrido_ms: int, total_ms: int) -> None:
        self.progresso.setRange(0, total_ms)
        self.progresso.setValue(decorrido_ms)
        self.progresso.show()
        self.preview.set_progresso(decorrido_ms / total_ms if total_ms else 1.0)
        restante = max(0, (total_ms - decorrido_ms + 999) // 1000)
        self.info(f"Mantenha o rosto ou o objeto dentro da moldura… {restante} s")

    def processando(self) -> None:
        self.progresso.setRange(0, 0)  # indeterminado
        self.progresso.show()
        self.info("Processando…")

    def ocioso(self) -> None:
        self.progresso.hide()


class CartaoResultado(QFrame):
    LADO = 150

    def __init__(self, posicao: int, caminho, porcentagem: float, parent=None):
        super().__init__(parent)
        self.setObjectName("cartao")
        self.setProperty("destaque", posicao == 1)
        self.porcentagem = porcentagem

        imagem = QLabel()
        imagem.setFixedSize(self.LADO, self.LADO)
        imagem.setPixmap(pixmap_arredondado(caminho, self.LADO))

        rotulo_pos = QLabel(f"#{posicao}")
        rotulo_pos.setObjectName("posicao")
        rotulo_pct = QLabel(f"{porcentagem:.0f}%")
        rotulo_pct.setObjectName("porcentagem")
        linha = QHBoxLayout()
        linha.addWidget(rotulo_pos, 0, Qt.AlignmentFlag.AlignBottom)
        linha.addStretch()
        linha.addWidget(rotulo_pct)

        barra = QProgressBar()
        barra.setObjectName("similaridade")
        barra.setTextVisible(False)
        barra.setRange(0, 100)
        barra.setValue(round(porcentagem))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(imagem, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(linha)
        layout.addWidget(barra)


class TelaResultados(QWidget):
    novo_scan = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.aviso = QLabel()
        self.aviso.setObjectName("aviso")
        self.aviso.hide()
        self.vazio = QLabel("Ainda não há itens no catálogo para comparar.")
        self.vazio.setObjectName("vazio")
        self.vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vazio.hide()
        self.resumo = QLabel()
        self.resumo.setObjectName("detalhes")
        self.resumo.setWordWrap(True)
        self.resumo.setTextFormat(Qt.TextFormat.RichText)
        self.resumo.hide()
        self._grade_widget = QWidget()
        self.grade = QGridLayout(self._grade_widget)
        self.grade.setSpacing(14)
        self.botao_novo = QPushButton("Novo scan")
        self.botao_novo.setObjectName("primario")
        self.botao_novo.setMinimumWidth(160)
        self.botao_novo.clicked.connect(self.novo_scan)

        rodape = QHBoxLayout()
        rodape.addStretch()
        rodape.addWidget(self.botao_novo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        cabecalho = _cabecalho("Itens mais parecidos", "")
        self.subtitulo = cabecalho.itemAt(1).widget()
        layout.addLayout(cabecalho)
        layout.addWidget(self.aviso)
        layout.addWidget(self.resumo)
        layout.addWidget(self.vazio)
        layout.addWidget(self._grade_widget, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(rodape)
        self.origem = "scan"
        self.definir_origem("scan")

    def definir_origem(self, origem: str, resumo: str = "") -> None:
        """'scan' ou 'comparacao': muda o subtítulo, o botão e o resumo exibido."""
        self.origem = origem
        if origem == "comparacao":
            self.subtitulo.setText("Ordenados pela similaridade com as imagens comparadas.")
            self.botao_novo.setText("Nova comparação")
        else:
            self.subtitulo.setText("Ordenados pela similaridade com o seu scan.")
            self.botao_novo.setText("Novo scan")
        self.resumo.setText(resumo)
        self.resumo.setVisible(bool(resumo))

    def cartoes(self) -> list[CartaoResultado]:
        return [
            self.grade.itemAt(i).widget()
            for i in range(self.grade.count())
            if isinstance(self.grade.itemAt(i).widget(), CartaoResultado)
        ]

    def mostrar(self, resultados) -> None:
        while self.grade.count():
            w = self.grade.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.aviso.hide()
        self.vazio.setVisible(not resultados)
        for n, r in enumerate(resultados):
            self.grade.addWidget(CartaoResultado(n + 1, r.caminho, r.porcentagem), n // 5, n % 5)

    def avisar(self, texto: str) -> None:
        self.aviso.setText(texto)
        self.aviso.show()


class TelaRemocao(QWidget):
    remover = Signal(int)
    voltar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lista = QListWidget()
        self.lista.setViewMode(QListWidget.ViewMode.IconMode)
        self.lista.setIconSize(QSize(110, 110))
        self.lista.setGridSize(QSize(140, 150))
        self.lista.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lista.setMovement(QListWidget.Movement.Static)
        self.lista.setSpacing(8)
        self.lista.itemSelectionChanged.connect(self._selecao)
        self.vazio = QLabel("Nenhum item criado por scan.")
        self.vazio.setObjectName("vazio")
        self.vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.botao_remover = QPushButton("Remover selecionado")
        self.botao_remover.setObjectName("perigo")
        self.botao_remover.setEnabled(False)
        self.botao_remover.clicked.connect(self._pedir_remocao)
        self.botao_voltar = QPushButton("Voltar")
        self.botao_voltar.clicked.connect(self.voltar)

        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_voltar)
        botoes.addStretch()
        botoes.addWidget(self.botao_remover)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(
            _cabecalho(
                "Itens criados por scan",
                "Selecione um item para removê-lo definitivamente do catálogo. "
                "Itens do catálogo inicial não aparecem aqui.",
            )
        )
        layout.addWidget(self.vazio)
        layout.addWidget(self.lista, 1)
        layout.addLayout(botoes)
        self.confirmacao: QDialog | None = None

    def mostrar(self, itens) -> None:
        self.lista.clear()
        for item in itens:
            icone = (
                QIcon(pixmap_arredondado(item.imagens[0].caminho, 110)) if item.imagens else QIcon()
            )
            w = QListWidgetItem(icone, item.nome)
            w.setData(Qt.ItemDataRole.UserRole, item.id)
            self.lista.addItem(w)
        self.vazio.setVisible(not itens)
        self.lista.setVisible(bool(itens))
        self._selecao()

    def _selecao(self) -> None:
        self.botao_remover.setEnabled(bool(self.lista.selectedItems()))

    def _pedir_remocao(self) -> None:
        selecionados = self.lista.selectedItems()
        if not selecionados:
            return
        item = selecionados[0]
        self.confirmacao = DialogoConfirmacao(
            f"<p style='font-size:17px; font-weight:700; color:{CORES['branco']}'>"
            f"Remover {item.text()}?</p>"
            "<p>As imagens e os dados do item serão apagados definitivamente e ele "
            "não aparecerá mais em nenhum resultado.</p>",
            "Remover",
            estilo_ok="perigo",
            parent=self,
        )
        item_id = item.data(Qt.ItemDataRole.UserRole)
        self.confirmacao.accepted.connect(lambda: self.remover.emit(item_id))
        self.confirmacao.open()


class DialogoConfirmacao(QDialog):
    def __init__(self, texto: str, rotulo_ok: str, estilo_ok: str = "primario", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirmar")
        self.setModal(True)
        self.setMinimumWidth(440)
        rotulo = QLabel(texto)
        rotulo.setWordWrap(True)
        rotulo.setTextFormat(Qt.TextFormat.RichText)
        botoes = QDialogButtonBox()
        self.botao_cancelar = botoes.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self.botao_ok = botoes.addButton(rotulo_ok, QDialogButtonBox.ButtonRole.AcceptRole)
        self.botao_ok.setObjectName(estilo_ok)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)
        layout.addWidget(rotulo)
        layout.addWidget(botoes)


class DialogoConsentimento(DialogoConfirmacao):
    def __init__(self, parent=None):
        super().__init__(TEXTO_CONSENTIMENTO, "Aceitar", estilo_ok="primario", parent=parent)
        self.setWindowTitle("Consentimento")
        self.botao_cancelar.setText("Recusar")
        self.setMinimumWidth(480)


def _imagens(n: int) -> str:
    return f"{n} imagem" if n == 1 else f"{n} imagens"


def eh_imagem(caminho) -> bool:
    from scanner.captura import EXTENSOES_IMAGEM

    return Path(caminho).suffix.lower() in EXTENSOES_IMAGEM


class AreaSoltar(QFrame):
    """Área que recebe imagens arrastadas e mostra as miniaturas."""

    soltas = Signal(list, int)  # caminhos de imagem, quantidade de arquivos ignorados
    MINIATURA = 84

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("areaSoltar")
        self.setAcceptDrops(True)
        self.setProperty("arrastando", False)
        self.dica = QLabel("Arraste para cá uma ou mais imagens de um mesmo objeto")
        self.dica.setObjectName("dicaSoltar")
        self.dica.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.miniaturas = QListWidget()
        self.miniaturas.setViewMode(QListWidget.ViewMode.IconMode)
        self.miniaturas.setIconSize(QSize(self.MINIATURA, self.MINIATURA))
        self.miniaturas.setGridSize(QSize(self.MINIATURA + 18, self.MINIATURA + 32))
        self.miniaturas.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.miniaturas.setMovement(QListWidget.Movement.Static)
        self.miniaturas.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.miniaturas.setAcceptDrops(False)
        self.miniaturas.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(self.dica, 1)
        layout.addWidget(self.miniaturas, 1)

    def _destacar(self, valor: bool) -> None:
        self.setProperty("arrastando", valor)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, evento) -> None:
        urls = evento.mimeData().urls() if evento.mimeData().hasUrls() else []
        if any(u.isLocalFile() and eh_imagem(u.toLocalFile()) for u in urls):
            evento.acceptProposedAction()
            self._destacar(True)
        else:
            evento.ignore()

    def dragLeaveEvent(self, evento) -> None:
        self._destacar(False)

    def dropEvent(self, evento) -> None:
        self._destacar(False)
        arquivos = [u.toLocalFile() for u in evento.mimeData().urls() if u.isLocalFile()]
        imagens = [a for a in arquivos if eh_imagem(a)]
        evento.acceptProposedAction()
        self.soltas.emit(imagens, len(arquivos) - len(imagens))

    def mostrar(self, caminhos) -> None:
        self.miniaturas.clear()
        for c in caminhos:
            item = QListWidgetItem(QIcon(pixmap_arredondado(c, self.MINIATURA, 8)), Path(c).name)
            item.setToolTip(str(c))
            self.miniaturas.addItem(item)
        self.miniaturas.setVisible(bool(caminhos))
        self.dica.setVisible(not caminhos)


class TelaComparacao(QWidget):
    """Escolha de uma ou mais imagens de um mesmo objeto para buscar no catálogo."""

    escolher = Signal()
    comparar = Signal()
    voltar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.caminhos: list[str] = []
        self.area = AreaSoltar()
        self.area.soltas.connect(self._soltas)
        self.contagem = QLabel()
        self.contagem.setObjectName("subtitulo")
        self.botao_escolher = QPushButton("Escolher imagens…")
        self.botao_escolher.clicked.connect(self.escolher)
        self.botao_limpar = QPushButton("Limpar")
        self.botao_limpar.clicked.connect(self.limpar)
        self.mensagem = QLabel()
        self.mensagem.setObjectName("mensagem")
        self.mensagem.setWordWrap(True)
        self.mensagem.setTextFormat(Qt.TextFormat.RichText)
        self.mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progresso = QProgressBar()
        self.progresso.setTextVisible(False)
        self.progresso.setRange(0, 0)
        self.progresso.hide()
        self.botao_voltar = QPushButton("Voltar")
        self.botao_voltar.clicked.connect(self.voltar)
        self.botao_comparar = QPushButton("Comparar")
        self.botao_comparar.setObjectName("primario")
        self.botao_comparar.setMinimumWidth(160)
        self.botao_comparar.clicked.connect(self.comparar)

        acoes = QHBoxLayout()
        acoes.addWidget(self.contagem)
        acoes.addStretch()
        acoes.addWidget(self.botao_limpar)
        acoes.addWidget(self.botao_escolher)
        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_voltar)
        botoes.addStretch()
        botoes.addWidget(self.botao_comparar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(
            _cabecalho(
                "Comparar imagens com o catálogo",
                "Use uma ou mais fotos de um mesmo objeto. Fotos ruins ou muito diferentes das "
                "demais são descartadas; se o objeto for novo (abaixo de 90%), ele entra no catálogo.",
            )
        )
        layout.addLayout(acoes)
        layout.addWidget(self.area, 1)
        layout.addWidget(self.mensagem)
        layout.addWidget(self.progresso)
        layout.addLayout(botoes)
        self._ocupado = False
        self.limpar()

    def _soltas(self, imagens: list, ignorados: int) -> None:
        self.adicionar(imagens)
        if ignorados:
            self.info(f"{ignorados} arquivo{'' if ignorados == 1 else 's'} ignorado{'' if ignorados == 1 else 's'}: não {'é' if ignorados == 1 else 'são'} imagem.", erro=True)

    def adicionar(self, caminhos) -> None:
        novos = [str(c) for c in caminhos if eh_imagem(c) and str(c) not in self.caminhos]
        self.caminhos.extend(novos)
        self.area.mostrar(self.caminhos)
        self.info("")
        self._atualizar()

    def limpar(self) -> None:
        self.caminhos = []
        self.area.mostrar([])
        self.info("")
        self._atualizar()

    def info(self, texto: str, erro: bool = False) -> None:
        self.mensagem.setText(texto)
        self.mensagem.setVisible(bool(texto))
        self.mensagem.setProperty("erro", erro)
        self.mensagem.style().unpolish(self.mensagem)
        self.mensagem.style().polish(self.mensagem)

    def _atualizar(self) -> None:
        n = len(self.caminhos)
        self.contagem.setText("Nenhuma imagem escolhida" if n == 0 else f"{_imagens(n)} escolhida{'' if n == 1 else 's'}")
        livre = not self._ocupado
        self.botao_comparar.setEnabled(livre and n > 0)
        self.botao_limpar.setEnabled(livre and n > 0)
        self.botao_escolher.setEnabled(livre)
        self.botao_voltar.setEnabled(livre)
        self.area.setAcceptDrops(livre)

    def processando(self) -> None:
        self._ocupado = True
        self.info("")
        self.progresso.show()
        self._atualizar()

    def ocioso(self) -> None:
        self._ocupado = False
        self.progresso.hide()
        self._atualizar()


def resumo_busca(r) -> str:
    """Texto do resumo da validação das imagens comparadas."""
    partes = [f"<b>Usadas:</b> {_imagens(len(r.usadas))}."]
    if r.descartadas_qualidade:
        lista = "; ".join(f"{html.escape(a)} ({html.escape(m)})" for a, m in r.descartadas_qualidade)
        partes.append(f"<b>Descartadas por qualidade:</b> {lista}.")
    if r.fora_do_grupo:
        lista = ", ".join(html.escape(a) for a in r.fora_do_grupo)
        partes.append(f"<b>Diferentes do grupo escolhido:</b> {lista}.")
    return "<br>".join(partes)


def mensagem_sem_validas(r) -> str:
    lista = "<br>".join(f"{html.escape(a)}: {html.escape(m)}" for a, m in r.descartadas_qualidade)
    return f"Nenhuma imagem válida, nada foi comparado.<br>{lista}"
