"""Gestion des sources (activer, désactiver, ajouter). La base est la source de vérité ;
`sources.yaml` n'en est que la valeur initiale (voir `sources_registry` dans le pipeline)."""
from datetime import datetime
from typing import Annotated, Any, Literal

from db.models import Source
from db.rules import CONNECTOR_KINDS
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["sources"])

Region = Literal["mdg", "lille", "remote", "global"]
Schedule = Literal["daily", "weekly"]


class SourcePatch(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    region: list[Region] | None = None
    priority: Annotated[int, Field(ge=1, le=3)] | None = None
    schedule: Schedule | None = None
    enabled: bool | None = None


class SourceIn(BaseModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_]{2,64}$")]
    name: str
    kind: str
    config: dict[str, Any] = {}
    region: list[Region] = []
    priority: Annotated[int, Field(ge=1, le=3)] = 2
    schedule: Schedule = "daily"
    enabled: bool = True

    @field_validator("kind")
    @classmethod
    def known_kind(cls, kind: str) -> str:
        if kind not in CONNECTOR_KINDS:
            raise ValueError(f"connecteur inconnu ; possibles : {', '.join(sorted(CONNECTOR_KINDS))}")
        return kind


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str | None
    kind: str
    config: dict[str, Any]  # les secrets restent sous forme ${VAR}
    region: list[str]
    priority: int | None
    schedule: str
    enabled: bool
    origin: str
    user_fields: list[str]
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    consecutive_empty_runs: int


@router.get("/sources/kinds")
def connector_kinds() -> list[str]:
    """Types de connecteurs écrits, seuls acceptés pour une nouvelle source."""
    return sorted(CONNECTOR_KINDS)


@router.get("/sources")
def list_sources(session: Annotated[Session, Depends(get_session)]) -> list[SourceOut]:
    rows = session.scalars(select(Source).order_by(Source.priority.nulls_last(), Source.id))
    return [SourceOut.model_validate(s) for s in rows]


@router.post("/sources", status_code=201)
def create_source(body: SourceIn, session: Annotated[Session, Depends(get_session)]) -> SourceOut:
    """Ajoutée en base seulement ; ingérée après le prochain passage de `sources_registry`."""
    if session.get(Source, body.id) is not None:
        raise HTTPException(409, "identifiant déjà pris")
    source = Source(**body.model_dump(), origin="api", user_fields=[])
    session.add(source)
    session.commit()
    return SourceOut.model_validate(source)


@router.patch("/sources/{source_id}")
def update_source(source_id: str, body: SourcePatch,
                  session: Annotated[Session, Depends(get_session)]) -> SourceOut:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "source inconnue")
    changes = body.model_dump(exclude_unset=True)
    if any(v is None for v in changes.values()):
        raise HTTPException(422, "valeur vide refusée")
    for key, value in changes.items():
        setattr(source, key, value)
    # ces champs ne seront plus repris de sources.yaml
    source.user_fields = sorted(set(source.user_fields or []) | set(changes))
    session.commit()
    return SourceOut.model_validate(source)
