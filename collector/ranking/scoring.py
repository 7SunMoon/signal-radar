from __future__ import annotations

from typing import Any


def calculate_final_score(scores: dict[str, Any], weights: dict[str, int]) -> float:
    """Convert 0–5 rubric values to a weighted 0–100 score."""
    total_weight = sum(weights.values()) or 1
    weighted = 0.0
    for dimension, weight in weights.items():
        value = float(scores.get(dimension, 0))
        weighted += max(0.0, min(5.0, value)) / 5.0 * weight
    return round(weighted / total_weight * 100, 1)
