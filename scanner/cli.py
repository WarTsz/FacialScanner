"""Linha de comando: `python -m scanner <comando>`.

Os imports pesados (torch, Qt, OpenCV) ficam dentro de cada comando para que
`--help` responda rápido.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scanner",
        description="Scanner de similaridade visual para rostos e objetos.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="caminho do config.toml (padrão: ./config.toml)",
    )
    sub = parser.add_subparsers(dest="comando", metavar="<comando>")

    p_app = sub.add_parser("app", help="abre a interface gráfica (padrão)")
    p_app.add_argument(
        "--camera",
        default=None,
        help="índice da câmera, arquivo de vídeo ou pasta de imagens (sobrepõe o config)",
    )

    sub.add_parser("preparar", help="baixa e guarda localmente os pesos dos modelos")

    p_seed = sub.add_parser("seed", help="importa itens a partir de uma pasta seed/<item>/*.jpg")
    p_seed.add_argument("pasta", type=Path, help="pasta com uma subpasta por item")

    sub.add_parser("calibrar", help="calcula as âncoras da %% de similaridade a partir do catálogo")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _criar_parser()
    args = parser.parse_args(argv)
    comando = args.comando or "app"

    if comando == "app":
        from scanner.gui.app import executar

        return executar(args.config, getattr(args, "camera", None))
    if comando == "preparar":
        from scanner.modelos import preparar

        return preparar(args.config)
    if comando == "seed":
        from scanner.catalogo import comando_seed

        return comando_seed(args.config, args.pasta)
    if comando == "calibrar":
        from scanner.calibracao import comando_calibrar

        return comando_calibrar(args.config)

    parser.print_help()
    return 2
