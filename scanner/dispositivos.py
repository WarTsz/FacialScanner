"""Detecção dos dispositivos de vídeo (câmeras) disponíveis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SYSFS_VIDEO = Path("/sys/class/video4linux")
MAX_INDICE_SONDADO = 10


@dataclass(frozen=True)
class Dispositivo:
    fonte: int | str  # índice da câmera no OpenCV, ou caminho de vídeo/pasta de imagens
    nome: str

    @property
    def rotulo(self) -> str:
        if isinstance(self.fonte, int):
            return f"{self.nome} (câmera {self.fonte})"
        return self.nome


def _ler(arquivo: Path, padrao: str = "") -> str:
    try:
        return arquivo.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return padrao


def _sondar_opencv(indice: int) -> bool:
    import cv2

    cap = cv2.VideoCapture(indice)
    try:
        return cap.isOpened()
    finally:
        cap.release()


def listar_dispositivos(
    raiz_sysfs: Path = SYSFS_VIDEO, sondar=None, max_indice: int = MAX_INDICE_SONDADO
) -> list[Dispositivo]:
    """Câmeras que capturam vídeo, ordenadas pelo índice.

    No Linux, lê o sysfs: usa o nome do dispositivo e mantém só os nós de captura
    (atributo `index` igual a 0; nós de metadados de webcams UVC têm `index` 1),
    sem abrir nenhuma câmera. Nos demais sistemas, testa os índices com o OpenCV.
    """
    raiz = Path(raiz_sysfs)
    if raiz.is_dir():
        encontrados = []
        for no in raiz.iterdir():
            m = re.fullmatch(r"video(\d+)", no.name)
            if not m or _ler(no / "index", "0") != "0":
                continue
            indice = int(m.group(1))
            encontrados.append(Dispositivo(indice, _ler(no / "name") or f"Câmera {indice}"))
        return sorted(encontrados, key=lambda d: d.fonte)
    sondar = sondar or _sondar_opencv
    return [Dispositivo(i, f"Câmera {i}") for i in range(max_indice) if sondar(i)]
