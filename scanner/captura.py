"""Captura: fonte de frames, processamento de cada frame e agregação do scan."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from scanner.config import Config
from scanner.embedding import Embedder, normalizar
from scanner.modelos import caminho_dino, caminho_yunet
from scanner.qualidade import Qualidade, avaliar
from scanner.recorte import DetectorRosto, recortar_moldura, recortar_rosto, rostos_na_moldura

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# --------------------------------------------------------------------------- fonte


class FonteIndisponivel(RuntimeError):
    pass


class FonteCamera:
    """Webcam (índice), arquivo de vídeo ou pasta de imagens (repetidas em ciclo)."""

    def __init__(self, fonte: int | str):
        self._imagens: list[np.ndarray] = []
        self._pos = 0
        self._cap = None
        if isinstance(fonte, str) and fonte.isdigit():
            fonte = int(fonte)
        if isinstance(fonte, str) and Path(fonte).is_dir():
            arquivos = sorted(
                p for p in Path(fonte).iterdir() if p.suffix.lower() in EXTENSOES_IMAGEM
            )
            self._imagens = [i for i in (cv2.imread(str(p)) for p in arquivos) if i is not None]
            if not self._imagens:
                raise FonteIndisponivel(f"Nenhuma imagem em {fonte}")
            return
        self._cap = cv2.VideoCapture(fonte)
        if not self._cap.isOpened():
            raise FonteIndisponivel(f"Câmera não encontrada ({fonte})")
        self._arquivo = isinstance(fonte, str)

    def ler(self) -> np.ndarray | None:
        if self._imagens:
            img = self._imagens[self._pos % len(self._imagens)]
            self._pos += 1
            return img.copy()
        ok, frame = self._cap.read()
        if not ok and self._arquivo:  # vídeo: volta ao início
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return frame if ok else None

    def liberar(self) -> None:
        if self._cap is not None:
            self._cap.release()


def instantes_amostragem(n: int, duracao_s: float) -> list[float]:
    """n instantes (s) uniformemente espaçados dentro da janela [0, duracao)."""
    passo = duracao_s / n
    return [passo * (i + 0.5) for i in range(n)]


# --------------------------------------------------------------------------- frames


@dataclass
class FrameProcessado:
    qualidade: Qualidade
    valido: bool
    motivo: str | None = None
    tem_rosto: bool = False
    recorte: np.ndarray | None = None
    vetor: np.ndarray | None = None


class ProcessadorFrames:
    """qualidade -> detecção de rosto -> recorte -> embedding. Não é thread-safe."""

    def __init__(self, cfg: Config, detector: DetectorRosto, embedder: Embedder):
        self.cfg = cfg
        self.detector = detector
        self.embedder = embedder

    @classmethod
    def criar(cls, cfg: Config) -> "ProcessadorFrames":
        detector = DetectorRosto(caminho_yunet(cfg), cfg.qualidade.rosto_confianca_min)
        return cls(cfg, detector, Embedder(caminho_dino(cfg)))

    def recortar(
        self, img: np.ndarray, fracao_moldura: float, rosto_na_moldura: bool = False
    ) -> FrameProcessado:
        """Qualidade e recorte, sem embedding.

        Com `rosto_na_moldura`, rostos com o centro fora da moldura são ignorados:
        o sujeito do scan é o que está enquadrado na tela, não um rosto ao fundo.
        """
        q = avaliar(img, self.cfg.qualidade)
        if not q.valido:
            return FrameProcessado(q, False, q.motivo)
        rostos = self.detector.detectar(img)
        if rosto_na_moldura:
            rostos = rostos_na_moldura(rostos, *img.shape[:2], fracao_moldura)
        rosto = rostos[0] if rostos else None
        if rosto is not None:
            if rosto.lado < self.cfg.qualidade.rosto_lado_min_px:
                return FrameProcessado(q, False, "rosto pequeno demais", tem_rosto=True)
            return FrameProcessado(q, True, tem_rosto=True, recorte=recortar_rosto(img, rosto))
        return FrameProcessado(q, True, recorte=recortar_moldura(img, fracao_moldura))

    def processar(
        self,
        img: np.ndarray,
        fracao_moldura: float | None = None,
        rosto_na_moldura: bool = False,
    ) -> FrameProcessado:
        fracao = self.cfg.captura.moldura_fracao if fracao_moldura is None else fracao_moldura
        fp = self.recortar(img, fracao, rosto_na_moldura)
        if fp.valido:
            fp.vetor = self.embedder.vetorizar_um(fp.recorte)
        return fp


# --------------------------------------------------------------------------- scan


class FalhaScan(RuntimeError):
    def __init__(self, validos: int, minimo: int, motivos: Counter):
        self.validos = validos
        self.minimo = minimo
        self.motivos = motivos
        super().__init__(f"apenas {validos} frames válidos (mínimo {minimo})")


@dataclass
class Scan:
    vetor: np.ndarray
    contem_rosto: bool
    frames: list[FrameProcessado]  # frames válidos da classe majoritária
    total_frames: int
    validos: int
    motivos_descarte: Counter = field(default_factory=Counter)

    def melhores(self, k: int) -> list[FrameProcessado]:
        return sorted(self.frames, key=lambda f: f.qualidade.pontuacao, reverse=True)[:k]

    def descartar(self) -> None:
        """Remove as imagens e vetores da memória."""
        self.frames.clear()
        self.vetor = np.zeros(0, np.float32)


def agregar(frames: list[FrameProcessado], minimo: int) -> Scan:
    """Junta os frames válidos em um vetor. Falha com menos de `minimo` válidos."""
    validos = [f for f in frames if f.valido and f.vetor is not None]
    motivos = Counter(f.motivo for f in frames if not f.valido)
    if len(validos) < minimo:
        raise FalhaScan(len(validos), minimo, motivos)
    com_rosto = [f for f in validos if f.tem_rosto]
    contem_rosto = len(com_rosto) > len(validos) / 2
    escolhidos = com_rosto if contem_rosto else [f for f in validos if not f.tem_rosto]
    vetor = normalizar(np.mean(np.stack([f.vetor for f in escolhidos]), axis=0))
    return Scan(vetor, contem_rosto, escolhidos, len(frames), len(validos), motivos)
