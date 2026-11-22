"""Agrupamento por semelhança das imagens escolhidas para a comparação com o catálogo."""

from __future__ import annotations

import numpy as np

from scanner.embedding import normalizar


def agrupar_por_semelhanca(vetores, escala, minimo: float) -> list[list[int]]:
    """Agrupamento de líder com centroide, na ordem das imagens.

    Cada vetor entra no grupo (entre os já formados) cuja média normalizada é a mais
    parecida, desde que a semelhança na escala calibrada atinja `minimo` (%).
    Senão, forma um grupo novo. Retorna os índices de cada grupo, na ordem de formação.
    """
    grupos: list[list[int]] = []
    centroides: list[np.ndarray] = []
    for i, v in enumerate(np.asarray(vetores, np.float32)):
        if centroides:
            pct = np.asarray(escala(np.stack(centroides) @ v), np.float64).reshape(-1)
            melhor = int(np.argmax(pct))  # em empate, o grupo formado primeiro
            if pct[melhor] >= minimo:
                grupos[melhor].append(i)
                membros = np.asarray(vetores, np.float32)[grupos[melhor]]
                centroides[melhor] = normalizar(membros.mean(axis=0))
                continue
        grupos.append([i])
        centroides.append(normalizar(v))
    return grupos


def escolher_grupo(grupos: list[list[int]]) -> int | None:
    """Índice do grupo com mais imagens; em empate, o formado primeiro."""
    if not grupos:
        return None
    return max(range(len(grupos)), key=lambda g: (len(grupos[g]), -g))
