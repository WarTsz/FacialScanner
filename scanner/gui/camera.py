"""Thread da câmera: lê frames continuamente para o preview e guarda o último."""

from __future__ import annotations

import threading

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from scanner.captura import FonteCamera, FonteIndisponivel

FALHAS_SEGUIDAS_MAX = 30


def para_qimage(frame_bgr: np.ndarray) -> QImage:
    h, w = frame_bgr.shape[:2]
    frame = np.ascontiguousarray(frame_bgr)
    return QImage(frame.data, w, h, frame.strides[0], QImage.Format.Format_BGR888).copy()


class ThreadCamera(QThread):
    frame_pronto = Signal(QImage)
    indisponivel = Signal(str)

    def __init__(self, fonte, intervalo_ms: int = 33, parent=None):
        super().__init__(parent)
        self._fonte_cfg = fonte
        self._intervalo_ms = intervalo_ms
        self._trava = threading.Lock()
        self._ultimo: np.ndarray | None = None
        self._seq = 0  # cresce a cada frame novo lido da fonte

    def ultimo_frame(self) -> np.ndarray | None:
        return self.ultimo_frame_numerado()[1]

    def ultimo_frame_numerado(self) -> tuple[int, np.ndarray | None]:
        """(número de sequência, cópia do último frame). O número muda a cada frame novo."""
        with self._trava:
            return self._seq, None if self._ultimo is None else self._ultimo.copy()

    def run(self) -> None:
        try:
            fonte = FonteCamera(self._fonte_cfg)
        except FonteIndisponivel as exc:
            self.indisponivel.emit(str(exc))
            return
        falhas = 0
        try:
            while not self.isInterruptionRequested():
                frame = fonte.ler()
                if frame is None:
                    falhas += 1
                    if falhas >= FALHAS_SEGUIDAS_MAX:
                        self.indisponivel.emit("A câmera parou de enviar imagens.")
                        return
                    self.msleep(self._intervalo_ms)
                    continue
                falhas = 0
                with self._trava:
                    self._ultimo = frame
                    self._seq += 1
                self.frame_pronto.emit(para_qimage(frame))
                self.msleep(self._intervalo_ms)
        finally:
            fonte.liberar()
            with self._trava:
                self._ultimo = None

    def parar(self) -> None:
        self.requestInterruption()
        self.wait(3000)
