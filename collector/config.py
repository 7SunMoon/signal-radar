from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_local_env(path: str | Path = ".env") -> None:
    """Load local KEY=VALUE pairs as the explicit configuration for a run."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    if not resolved.exists():
        return
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            # Empty values intentionally disable inherited credentials.
            os.environ[key] = value


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    with resolved.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_sources() -> dict[str, Any]:
    return load_yaml("config/sources.yaml")


def load_ranking() -> dict[str, Any]:
    return load_yaml("config/ranking.yaml")
