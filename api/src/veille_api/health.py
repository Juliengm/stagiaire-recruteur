"""État des sources : dernière réussite, échecs et passages à vide consécutifs."""
from datetime import datetime
from typing import Annotated

from db.models import Source
from db.rules import FAILURES_ALERT, SILENT_AFTER_RUNS
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["sources"])


class SourceHealthOut(BaseModel):
    id: str
    name: str | None
    kind: str
    enabled: bool
    last_success_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    consecutive_empty_runs: int
    failing: bool
    silent: bool


@router.get("/health/sources")
def sources_health(session: Annotated[Session, Depends(get_session)]) -> list[SourceHealthOut]:
    out = []
    for s in session.scalars(select(Source).order_by(Source.id)):
        silent_after = int((s.config or {}).get("silent_after_runs", SILENT_AFTER_RUNS))
        out.append(SourceHealthOut(
            id=s.id, name=s.name, kind=s.kind, enabled=s.enabled,
            last_success_at=s.last_success_at, last_error=s.last_error,
            consecutive_failures=s.consecutive_failures,
            consecutive_empty_runs=s.consecutive_empty_runs,
            failing=s.consecutive_failures >= FAILURES_ALERT,
            silent=s.consecutive_empty_runs >= silent_after,
        ))
    return out
