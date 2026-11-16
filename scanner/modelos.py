"""Localização e download dos pesos dos modelos pré-treinados."""

from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from scanner.config import Config, carregar_config

YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_ARQUIVO = "face_detection_yunet_2023mar.onnx"

DINO_REPO = "timm/vit_small_patch14_dinov2.lvd142m"
DINO_ARQUIVO = "model.safetensors"
DINO_MODELO_TIMM = "vit_small_patch14_dinov2.lvd142m"


class ModelosAusentes(RuntimeError):
    """Pesos não encontrados; rode `python -m scanner preparar`."""


def caminho_yunet(cfg: Config) -> Path:
    return cfg.modelos.diretorio / YUNET_ARQUIVO


def caminho_dino(cfg: Config) -> Path:
    return cfg.modelos.diretorio / "dinov2-vits14" / DINO_ARQUIVO


def exigir(caminho: Path) -> Path:
    if not caminho.exists():
        raise ModelosAusentes(
            f"Modelo não encontrado em {caminho}. Rode `python -m scanner preparar`."
        )
    return caminho


def _baixar_url(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destino.parent, delete=False) as tmp:
        with urllib.request.urlopen(url, timeout=60) as resp:
            shutil.copyfileobj(resp, tmp)
    Path(tmp.name).chmod(0o644)
    Path(tmp.name).replace(destino)


def _baixar_dino(destino: Path) -> None:
    from huggingface_hub import hf_hub_download

    destino.parent.mkdir(parents=True, exist_ok=True)
    baixado = hf_hub_download(DINO_REPO, DINO_ARQUIVO, local_dir=destino.parent)
    if Path(baixado) != destino:
        Path(baixado).replace(destino)


def garantir_modelos(cfg: Config, saida=sys.stdout) -> list[str]:
    """Baixa os pesos que faltam. Retorna os nomes dos que foram baixados agora."""
    baixados: list[str] = []
    itens = [
        ("YuNet (detecção de rosto)", caminho_yunet(cfg), lambda d: _baixar_url(YUNET_URL, d)),
        ("DINOv2 ViT-S/14 (embedding)", caminho_dino(cfg), _baixar_dino),
    ]
    for nome, destino, baixar in itens:
        if destino.exists() and destino.stat().st_size > 0:
            print(f"[ok] {nome}: já presente em {destino}", file=saida)
            continue
        print(f"[..] {nome}: baixando para {destino}", file=saida)
        baixar(destino)
        baixados.append(nome)
        print(f"[ok] {nome}: baixado ({destino.stat().st_size / 1e6:.1f} MB)", file=saida)
    return baixados


def preparar(caminho_config: Path | None) -> int:
    cfg = carregar_config(caminho_config)
    try:
        baixados = garantir_modelos(cfg)
    except Exception as exc:  # rede, disco, etc.
        print(f"Falha ao preparar os modelos: {exc}", file=sys.stderr)
        return 1
    if not baixados:
        print("Nada a baixar: todos os modelos já estão presentes.")
    return 0
