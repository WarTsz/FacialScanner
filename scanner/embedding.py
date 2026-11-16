"""Embedding visual com DINOv2 ViT-S/14: um vetor de 384 dimensões por recorte."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from scanner.modelos import DINO_MODELO_TIMM, exigir

DIMENSAO = 384
ENTRADA = 224
_MEDIA = np.array([0.485, 0.456, 0.406], np.float32)
_DESVIO = np.array([0.229, 0.224, 0.225], np.float32)


def normalizar(v: np.ndarray) -> np.ndarray:
    """Normalização L2 por linha (ou do vetor, se 1D)."""
    norma = np.linalg.norm(v, axis=-1, keepdims=True)
    return (v / np.maximum(norma, 1e-12)).astype(np.float32)


class Embedder:
    """Carrega o DINOv2 a partir dos pesos locais. Não é thread-safe."""

    def __init__(self, caminho_pesos: Path, dispositivo: str | None = None):
        import timm
        import torch

        self._torch = torch
        self.dispositivo = dispositivo or ("cuda" if torch.cuda.is_available() else "cpu")
        self.modelo = timm.create_model(
            DINO_MODELO_TIMM,
            pretrained=True,
            num_classes=0,
            img_size=ENTRADA,
            pretrained_cfg_overlay={"file": str(exigir(Path(caminho_pesos)))},
        )
        self.modelo.eval().to(self.dispositivo)

    @staticmethod
    def _preprocessar(recorte_bgr: np.ndarray) -> np.ndarray:
        h, w = recorte_bgr.shape[:2]
        interp = cv2.INTER_AREA if max(h, w) > ENTRADA else cv2.INTER_LINEAR
        img = cv2.resize(recorte_bgr, (ENTRADA, ENTRADA), interpolation=interp)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - _MEDIA) / _DESVIO
        return img.transpose(2, 0, 1)

    def vetorizar(self, recortes: list[np.ndarray]) -> np.ndarray:
        """Retorna uma matriz (N, 384) float32 com linhas de norma 1."""
        if not recortes:
            return np.zeros((0, DIMENSAO), np.float32)
        lote = np.stack([self._preprocessar(r) for r in recortes])
        torch = self._torch
        with torch.inference_mode():
            saida = self.modelo(torch.from_numpy(lote).to(self.dispositivo))
        return normalizar(saida.float().cpu().numpy())

    def vetorizar_um(self, recorte: np.ndarray) -> np.ndarray:
        return self.vetorizar([recorte])[0]
