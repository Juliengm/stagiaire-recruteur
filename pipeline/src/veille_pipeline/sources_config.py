"""Lecture de sources.yaml (valeur initiale de la table `sources`) et résolution des ${VAR}.

La base est la source de vérité : les ${VAR} y restent tels quels (pas de secret en base),
ils ne sont résolus depuis l'environnement qu'au moment d'appeler le connecteur.
"""
import os
import re
from pathlib import Path
from typing import Any

import yaml
from db.models import Source

_VAR = re.compile(r"\$\{(\w+)\}")

# champs de la table repris du YAML, sauf s'ils ont été modifiés depuis l'interface
SYNCED_FIELDS = ("name", "kind", "config", "region", "priority", "schedule", "enabled")


def resolve_vars(value: Any) -> Any:
    if isinstance(value, str):
        return _VAR.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: resolve_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_vars(v) for v in value]
    return value


def load_defaults(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()).get("defaults", {})


def load_sources(path: Path, resolve: bool = True) -> list[dict[str, Any]]:
    """Retourne les sources avec les valeurs par défaut appliquées."""
    doc = yaml.safe_load(path.read_text())
    defaults = doc.get("defaults", {})
    sources = []
    for raw in doc["sources"]:
        merged = {**defaults, **raw}
        sources.append(resolve_vars(merged) if resolve else merged)
    return sources


def source_from_row(row: Source, defaults: dict[str, Any]) -> dict[str, Any]:
    """Source telle que l'attendent les connecteurs, depuis la base (${VAR} résolues)."""
    return resolve_vars({
        **defaults, "id": row.id, "name": row.name, "kind": row.kind, "config": row.config or {},
        "region": row.region, "priority": row.priority, "schedule": row.schedule,
        "enabled": row.enabled,
    })


def sync_yaml_to_rows(yaml_sources: list[dict[str, Any]],
                      rows: dict[str, Source]) -> tuple[list[Source], list[str]]:
    """Applique le YAML aux lignes existantes (hors champs modifiés dans l'interface).

    Retourne les nouvelles lignes à insérer et les sources issues du YAML qui n'y sont plus
    (désactivées). Les sources ajoutées depuis l'interface (`origin = 'api'`) ne sont pas touchées.
    """
    new_rows = []
    for src in yaml_sources:
        values = {
            "name": src.get("name"), "kind": src["kind"], "config": src.get("config", {}),
            "region": src.get("region", []), "priority": src.get("priority"),
            "schedule": src.get("schedule", "daily"), "enabled": src.get("enabled", True),
        }
        row = rows.get(src["id"])
        if row is None:
            new_rows.append(Source(id=src["id"], origin="yaml", user_fields=[], **values))
            continue
        for field_name in SYNCED_FIELDS:
            if field_name not in (row.user_fields or []):
                setattr(row, field_name, values[field_name])
    in_yaml = {s["id"] for s in yaml_sources}
    removed = [r.id for r in rows.values()
               if r.origin == "yaml" and r.id not in in_yaml and r.enabled]
    for source_id in removed:
        rows[source_id].enabled = False
    return new_rows, removed
