"""Telas do aplicativo: câmera, resultados, remoção e diálogo de consentimento."""

from __future__ import annotations

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

    def __init__(self, fracao_moldura: float, parent=None):
        super().__init__(parent)
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

        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_gerenciar)
        botoes.addWidget(self.botao_adicionar)
        botoes.addStretch()
        botoes.addWidget(self.botao_escanear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
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
        self.info(f"Câmera não encontrada. Conecte uma webcam e reabra o aplicativo.\n({motivo})", True)

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
        layout.addLayout(_cabecalho("Itens mais parecidos", "Ordenados pela similaridade com o seu scan."))
        layout.addWidget(self.aviso)
        layout.addWidget(self.vazio)
        layout.addWidget(self._grade_widget, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(rodape)

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
