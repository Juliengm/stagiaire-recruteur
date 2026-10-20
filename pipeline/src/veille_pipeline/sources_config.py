"""Lecture de sources.yaml avec résolution des ${VAR} depuis l'environnement."""
import os
import re
from pathlib import Path
from typing import Any

import yaml

_VAR = re.compile(r"\$\{(\w+)\}")


def _resolve(value: Any) -> Any:
    if isinstance(value, str):
        return _VAR.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v) for v in value]
    return value


def load_sources(path: Path) -> list[dict[str, Any]]:
    """Retourne les sources avec les valeurs par défaut appliquées."""
    doc = yaml.safe_load(path.read_text())
    defaults = doc.get("defaults", {})
    sources = []
    for raw in doc["sources"]:
        merged = {**defaults, **raw}
        sources.append(_resolve(merged))
    return sources
