"""Tema escuro (inspirado em Discord / VS Code) com destaques em branco, ciano e rosa."""

from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPalette

RECURSOS = Path(__file__).parent / "recursos"
TAMANHOS_ICONE = (16, 24, 32, 48, 64, 128, 256)

CORES = {
    "fundo": "#1e1f22",  # base da janela
    "barra": "#18191c",  # cabeçalho e barra de status
    "superficie": "#2b2d31",  # painéis, listas, diálogos
    "elevado": "#313338",  # cartões
    "borda": "#3f4147",
    "hover": "#404249",
    "botao": "#3a3c42",
    "botao_hover": "#45474e",
    "desabilitado": "#5c5f66",
    "texto": "#f2f3f5",
    "texto_suave": "#b5bac1",
    "texto_mudo": "#80848e",
    "branco": "#ffffff",
    "ciano": "#5ce1e6",
    "ciano_claro": "#8ff0f3",
    "rosa": "#ff79c6",
    "rosa_claro": "#ffa3da",
    "perigo": "#f23f6b",
    "perigo_hover": "#ff5c85",
    "preview": "#111214",
}

_QSS = Template(
    """
* { font-family: "Inter", "Segoe UI", "Noto Sans", "Helvetica Neue", sans-serif; }
QWidget { font-size: 14px; color: $texto; }
QMainWindow, QStackedWidget, QStackedWidget > QWidget { background: $fundo; }
QLabel { background: transparent; }

/* cabeçalho e barra de status */
QFrame#cabecalho { background: $barra; border-bottom: 1px solid $borda; }
QLabel#marca { font-size: 15px; font-weight: 700; letter-spacing: 1px; }
QLabel#secao { color: $texto_mudo; font-size: 13px; }
QStatusBar { background: $barra; color: $texto_suave; border-top: 1px solid $borda; }
QStatusBar::item { border: none; }
QStatusBar QLabel { font-size: 12px; padding: 2px 10px; color: $texto_suave; }

/* títulos e textos */
QLabel#titulo { font-size: 22px; font-weight: 700; color: $branco; }
QLabel#subtitulo { color: $texto_mudo; font-size: 13px; }
QLabel#mensagem { color: $texto_suave; padding: 6px; font-size: 15px; }
QLabel#mensagem[erro="true"] { color: $perigo; }
QLabel#vazio { color: $texto_mudo; font-size: 15px; padding: 48px; }
QLabel#aviso {
    background: rgba(92, 225, 230, 0.10); color: $ciano;
    border-left: 4px solid $ciano; border-radius: 6px;
    padding: 10px 14px; font-weight: 600;
}

/* preview da câmera */
QLabel#preview {
    background: $preview; border: 1px solid $borda; border-radius: 14px;
    color: $texto_mudo; font-size: 16px;
}

/* cartões de resultado */
QFrame#cartao { background: $elevado; border: 1px solid $borda; border-radius: 12px; }
QFrame#cartao:hover { border: 1px solid $ciano; }
QFrame#cartao[destaque="true"] { border: 2px solid $rosa; }
QLabel#posicao { color: $texto_mudo; font-size: 12px; font-weight: 700; }
QLabel#porcentagem { font-size: 20px; font-weight: 700; color: $branco; }
QFrame#cartao[destaque="true"] QLabel#porcentagem { color: $rosa; }

/* botões */
QPushButton {
    background: $botao; color: $texto; border: none; border-radius: 8px;
    padding: 9px 22px; font-weight: 600;
}
QPushButton:hover { background: $botao_hover; }
QPushButton:pressed { background: $hover; }
QPushButton:disabled { background: $superficie; color: $desabilitado; }
QPushButton#primario {
    color: $preview;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $ciano, stop:1 $rosa);
}
QPushButton#primario:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $ciano_claro, stop:1 $rosa_claro);
}
QPushButton#primario:disabled { background: $superficie; color: $desabilitado; }
QPushButton#perigo { background: $perigo; color: $branco; }
QPushButton#perigo:hover { background: $perigo_hover; }
QPushButton#perigo:disabled { background: $superficie; color: $desabilitado; }

/* barras de progresso */
QProgressBar { background: $superficie; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }
QProgressBar::chunk {
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $ciano, stop:1 $rosa);
}
QProgressBar#similaridade { max-height: 4px; min-height: 4px; background: $borda; }

/* lista de câmeras */
QComboBox {
    background: $botao; color: $texto; border: 1px solid $borda; border-radius: 8px;
    padding: 7px 12px; min-height: 22px;
}
QComboBox:hover { border: 1px solid $ciano; }
QComboBox:disabled { background: $superficie; color: $desabilitado; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url($seta); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $superficie; color: $texto; border: 1px solid $borda;
    selection-background-color: rgba(255, 121, 198, 0.22); selection-color: $branco; outline: 0;
}

/* comparação de imagens */
QFrame#areaSoltar { background: $superficie; border: 2px dashed $borda; border-radius: 14px; }
QFrame#areaSoltar[arrastando="true"] { border: 2px dashed $ciano; background: rgba(92, 225, 230, 0.06); }
QFrame#areaSoltar QListWidget { background: transparent; border: none; }
QLabel#dicaSoltar { color: $texto_mudo; font-size: 16px; }
QFrame#lado { background: $superficie; border: 1px solid $borda; border-radius: 12px; }
QFrame#lado QListWidget { background: $elevado; border: none; border-radius: 8px; padding: 6px; }
QFrame#resultadoComparacao { background: $elevado; border: 1px solid $borda; border-radius: 12px; }
QLabel#porcentagemGrande { font-size: 44px; font-weight: 800; min-width: 130px; }
QLabel#interpretacao { color: $branco; font-size: 15px; font-weight: 600; }
QLabel#detalhes { color: $texto_suave; font-size: 13px; }

/* lista de remoção */
QListWidget {
    background: $superficie; border: 1px solid $borda; border-radius: 12px;
    padding: 10px; outline: 0;
}
QListWidget::item { color: $texto_suave; border-radius: 8px; padding: 6px; }
QListWidget::item:hover { background: $hover; }
QListWidget::item:selected {
    background: rgba(255, 121, 198, 0.16); color: $branco; border: 1px solid $rosa;
}

/* diálogos */
QDialog { background: $superficie; }
QDialog QLabel { color: $texto_suave; font-size: 14px; }

/* barras de rolagem finas (VS Code) */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle { background: #4e5058; border-radius: 4px; min-height: 30px; min-width: 30px; }
QScrollBar::handle:hover { background: $texto_mudo; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: $barra; color: $texto; border: 1px solid $borda; padding: 4px 8px; }
"""
)

ESTILO = _QSS.substitute(CORES, seta=(RECURSOS / "seta.svg").as_posix())


def paleta() -> QPalette:
    c = {k: QColor(v) for k, v in CORES.items()}
    p = QPalette()
    papeis = {
        QPalette.ColorRole.Window: c["fundo"],
        QPalette.ColorRole.WindowText: c["texto"],
        QPalette.ColorRole.Base: c["superficie"],
        QPalette.ColorRole.AlternateBase: c["elevado"],
        QPalette.ColorRole.Text: c["texto"],
        QPalette.ColorRole.Button: c["botao"],
        QPalette.ColorRole.ButtonText: c["texto"],
        QPalette.ColorRole.Highlight: c["rosa"],
        QPalette.ColorRole.HighlightedText: c["preview"],
        QPalette.ColorRole.ToolTipBase: c["barra"],
        QPalette.ColorRole.ToolTipText: c["texto"],
        QPalette.ColorRole.PlaceholderText: c["texto_mudo"],
        QPalette.ColorRole.Link: c["ciano"],
        QPalette.ColorRole.BrightText: c["branco"],
    }
    for papel, cor in papeis.items():
        p.setColor(papel, cor)
    for papel in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, papel, c["desabilitado"])
    return p


def icone_app() -> QIcon:
    """Ícone do aplicativo (janela, painel e alternador de janelas) em vários tamanhos."""
    icone = QIcon()
    for n in TAMANHOS_ICONE:
        arquivo = RECURSOS / f"icone-{n}.png"
        if arquivo.exists():
            icone.addFile(str(arquivo), QSize(n, n))
    return icone


def aplicar_tema(app) -> None:
    app.setStyle("Fusion")
    app.setPalette(paleta())
    app.setStyleSheet(ESTILO)
    app.setWindowIcon(icone_app())
