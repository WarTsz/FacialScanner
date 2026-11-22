"""Carregamento do config.toml com valores padrão para chaves ausentes."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path

CAMINHO_PADRAO = Path("config.toml")


@dataclass
class CameraCfg:
    fonte: int | str = 0
    ativa: bool = True


@dataclass
class CapturaCfg:
    duracao_s: float = 5.0
    n_frames: int = 15
    min_frames_validos: int = 5
    moldura_fracao: float = 0.6


@dataclass
class QualidadeCfg:
    nitidez_min: float = 25.0
    brilho_min: float = 40.0
    brilho_max: float = 220.0
    rosto_confianca_min: float = 0.8
    rosto_lado_min_px: int = 80


@dataclass
class CatalogoCfg:
    diretorio_dados: Path = Path("data")
    imagens_por_item: int = 3


@dataclass
class RankingCfg:
    top: int = 10
    limiar_insercao: float = 90.0


@dataclass
class ComparacaoCfg:
    similaridade_minima: float = 50.0


@dataclass
class CalibracaoCfg:
    cos_zero: float = 0.0
    cos_noventa: float = 0.7


@dataclass
class ModelosCfg:
    diretorio: Path = Path("models")


@dataclass
class Config:
    camera: CameraCfg = field(default_factory=CameraCfg)
    captura: CapturaCfg = field(default_factory=CapturaCfg)
    qualidade: QualidadeCfg = field(default_factory=QualidadeCfg)
    catalogo: CatalogoCfg = field(default_factory=CatalogoCfg)
    ranking: RankingCfg = field(default_factory=RankingCfg)
    calibracao: CalibracaoCfg = field(default_factory=CalibracaoCfg)
    comparacao: ComparacaoCfg = field(default_factory=ComparacaoCfg)
    modelos: ModelosCfg = field(default_factory=ModelosCfg)
    caminho: Path | None = None


def _preencher(secao, valores: dict, base: Path):
    for f in fields(secao):
        if f.name not in valores:
            continue
        valor = valores[f.name]
        atual = getattr(secao, f.name)
        if isinstance(atual, Path):
            valor = Path(valor)
            if not valor.is_absolute():
                valor = base / valor
        elif isinstance(atual, float) and isinstance(valor, int):
            valor = float(valor)
        setattr(secao, f.name, valor)


def carregar_config(caminho: Path | str | None = None) -> Config:
    """Lê o config.toml. Arquivo ou chaves ausentes assumem os valores padrão."""
    caminho = Path(caminho) if caminho else CAMINHO_PADRAO
    cfg = Config(caminho=caminho.resolve())
    base = caminho.resolve().parent
    dados: dict = {}
    if caminho.exists():
        with open(caminho, "rb") as fp:
            dados = tomllib.load(fp)
    for f in fields(cfg):
        secao = getattr(cfg, f.name)
        if not is_dataclass(secao):
            continue
        # Caminhos padrão também são relativos à pasta do config.
        for sf in fields(secao):
            v = getattr(secao, sf.name)
            if isinstance(v, Path) and not v.is_absolute():
                setattr(secao, sf.name, base / v)
        _preencher(secao, dados.get(f.name, {}), base)
    return cfg


def _valor_toml(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.4f}"
    if isinstance(v, int):
        return str(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def atualizar_secao(caminho: Path, secao: str, valores: dict) -> None:
    """Grava chaves em uma seção do config.toml, preservando o resto do arquivo."""
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8") if caminho.exists() else ""
    linhas = {k: f"{k} = {_valor_toml(v)}" for k, v in valores.items()}

    achada = re.search(rf"^\[{re.escape(secao)}\][^\n]*\n(.*?)(?=^\[|\Z)", texto, re.S | re.M)
    if not achada:
        bloco = f"\n[{secao}]\n" + "".join(l + "\n" for l in linhas.values())
        caminho.write_text(texto.rstrip("\n") + "\n" + bloco, encoding="utf-8")
        return

    corpo = achada.group(1)
    for chave, linha in linhas.items():
        corpo, n = re.subn(rf"^{re.escape(chave)}\s*=.*$", lambda _m, l=linha: l, corpo, flags=re.M)
        if n == 0:
            corpo = corpo.rstrip("\n") + f"\n{linha}\n"
    texto = texto[: achada.start(1)] + corpo + texto[achada.end(1) :]
    caminho.write_text(texto, encoding="utf-8")


def atualizar_calibracao(caminho: Path, cos_zero: float, cos_noventa: float) -> None:
    """Grava as âncoras na seção [calibracao], preservando o resto do arquivo."""
    atualizar_secao(caminho, "calibracao", {"cos_zero": float(cos_zero), "cos_noventa": float(cos_noventa)})


def atualizar_camera(caminho: Path, fonte: int | str, ativa: bool) -> None:
    """Grava a câmera escolhida e se ela está ativa na seção [camera]."""
    atualizar_secao(caminho, "camera", {"fonte": fonte, "ativa": bool(ativa)})
