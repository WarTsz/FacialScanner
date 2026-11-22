"""Trabalhador em thread própria: roda modelos, busca e inserção fora da GUI.

Uma única thread processa os pedidos na ordem em que chegam, então `concluir`
sempre roda depois de todos os frames do scan enviados antes dele.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

from scanner.captura import FalhaScan
from scanner.motor import Motor

log = logging.getLogger(__name__)


class Trabalhador(QObject):
    pronto = Signal()
    erro_fatal = Signal(str)
    concluido = Signal(object)  # ResultadoScan
    falhou = Signal(object)  # FalhaScan
    inserido = Signal(object)  # Item
    adicionado = Signal(object)  # ResultadoAdicao
    comparado = Signal(object)  # ResultadoBuscaImagens
    erro = Signal(str)

    def __init__(self, cfg, fabrica_motor=Motor.criar):
        super().__init__()
        self._cfg = cfg
        self._fabrica = fabrica_motor
        self._frames: list = []
        self.motor: Motor | None = None

    @Slot()
    def iniciar(self) -> None:
        try:
            self.motor = self._fabrica(self._cfg)
        except Exception as exc:  # modelos ausentes, banco inacessível...
            log.exception("falha ao iniciar o motor")
            self.erro_fatal.emit(str(exc))
            return
        self.pronto.emit()

    @Slot()
    def novo_scan(self) -> None:
        self._frames = []

    @Slot(object)
    def processar(self, frame) -> None:
        try:
            self._frames.append(self.motor.processar_frame(frame))
        except Exception:
            log.exception("falha ao processar frame; frame ignorado")

    @Slot()
    def concluir(self) -> None:
        frames, self._frames = self._frames, []
        try:
            self.concluido.emit(self.motor.concluir(frames))
        except FalhaScan as falha:
            self.falhou.emit(falha)
        except Exception as exc:
            log.exception("falha ao concluir scan")
            self.erro.emit(str(exc))
        finally:
            frames.clear()

    @Slot(object)
    def inserir(self, scan) -> None:
        try:
            self.inserido.emit(self.motor.inserir(scan))
        except Exception as exc:
            log.exception("falha ao inserir scan")
            scan.descartar()
            self.erro.emit(f"Não foi possível adicionar ao catálogo: {exc}")

    @Slot(object)
    def adicionar_imagens(self, caminhos) -> None:
        try:
            self.adicionado.emit(self.motor.adicionar_imagens(caminhos))
        except Exception as exc:
            log.exception("falha ao adicionar imagens")
            self.erro.emit(f"Não foi possível adicionar as imagens: {exc}")

    @Slot(object)
    def comparar(self, caminhos) -> None:
        try:
            self.comparado.emit(self.motor.buscar_por_imagens(caminhos))
        except Exception as exc:
            log.exception("falha ao comparar imagens")
            self.erro.emit(f"Não foi possível comparar as imagens: {exc}")

    @Slot(object)
    def descartar(self, scan) -> None:
        self.motor.descartar(scan)

    @Slot()
    def encerrar(self) -> None:
        if self.motor is not None:
            self.motor.fechar()
