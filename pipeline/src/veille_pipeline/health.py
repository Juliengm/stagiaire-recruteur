"""Règles de santé des sources et des offres normalisées (alimentent les asset checks)."""
from dataclasses import dataclass
from datetime import date

from db.rules import FAILURES_ALERT, SILENT_AFTER_RUNS


@dataclass(frozen=True)
class SourceHealth:
    id: str
    consecutive_failures: int
    consecutive_empty_runs: int
    silent_after_runs: int = SILENT_AFTER_RUNS


def silent_sources(sources: list[SourceHealth]) -> list[str]:
    return [s.id for s in sources if s.consecutive_empty_runs >= s.silent_after_runs]


def failing_sources(sources: list[SourceHealth]) -> list[str]:
    return [s.id for s in sources if s.consecutive_failures >= FAILURES_ALERT]


def invalid_offer_reasons(title: str | None, url: str | None,
                          posted_at: date | None, deadline: date | None) -> list[str]:
    reasons = []
    if not (title or "").strip():
        reasons.append("titre vide")
    if not (url or "").strip():
        reasons.append("URL vide")
    if posted_at and deadline and deadline < posted_at:
        reasons.append("date limite antérieure à la publication")
    return reasons
