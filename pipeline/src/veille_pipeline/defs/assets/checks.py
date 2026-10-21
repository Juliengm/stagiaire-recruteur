import dagster as dg
from db.models import Offer, Source
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from veille_pipeline.connectors import CONNECTORS
from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.ingest import raw_offers
from veille_pipeline.defs.assets.process import offers_deduped, offers_normalized
from veille_pipeline.health import (
    SILENT_AFTER_RUNS,
    SourceHealth,
    failing_sources,
    invalid_offer_reasons,
    silent_sources,
)

MAX_DUPLICATE_RATE = 0.60


@dg.asset_check(asset=offers_deduped, description="Taux de doublons plausible (alerte au-delà de 60 %).")
def duplicate_rate_plausible() -> dg.AssetCheckResult:
    with Session(get_engine()) as session:
        total = session.scalar(select(func.count()).select_from(Offer)) or 0
        dupes = session.scalar(
            select(func.count()).select_from(Offer).where(Offer.duplicate_of.is_not(None))) or 0
    rate = dupes / total if total else 0.0
    return dg.AssetCheckResult(
        passed=rate <= MAX_DUPLICATE_RATE, severity=dg.AssetCheckSeverity.WARN,
        metadata={"taux_doublons": rate, "doublons": dupes, "offres": total})


def _ingestible_sources() -> list[SourceHealth]:
    with Session(get_engine()) as session:
        rows = session.scalars(select(Source).where(Source.enabled.is_(True)))
        return [SourceHealth(
            s.id, s.consecutive_failures, s.consecutive_empty_runs,
            int((s.config or {}).get("silent_after_runs", SILENT_AFTER_RUNS)))
            for s in rows if s.kind in CONNECTORS]


@dg.asset_check(
    asset=raw_offers, name="stagiaire_en_pause_cafe",
    description="Aucune source active ne reste muette (aucune offre nouvelle) 3 exécutions de suite.")
def stagiaire_en_pause_cafe() -> dg.AssetCheckResult:
    silent = silent_sources(_ingestible_sources())
    return dg.AssetCheckResult(
        passed=not silent, severity=dg.AssetCheckSeverity.WARN,
        metadata={"sources_muettes": ", ".join(silent) or "aucune"})


@dg.asset_check(asset=raw_offers, description="Aucune source en échec 3 exécutions de suite.")
def sources_without_consecutive_failures() -> dg.AssetCheckResult:
    failing = failing_sources(_ingestible_sources())
    return dg.AssetCheckResult(
        passed=not failing, severity=dg.AssetCheckSeverity.WARN,
        metadata={"sources_en_echec": ", ".join(failing) or "aucune"})


@dg.asset_check(
    asset=offers_normalized,
    description="Titre et URL non vides, date limite postérieure à la publication.")
def offers_normalized_valid() -> dg.AssetCheckResult:
    bad: dict[int, list[str]] = {}
    with Session(get_engine()) as session:
        for o in session.scalars(select(Offer)):
            reasons = invalid_offer_reasons(o.title, o.canonical_url, o.posted_at, o.deadline)
            if reasons:
                bad[o.id] = reasons
    return dg.AssetCheckResult(
        passed=not bad, severity=dg.AssetCheckSeverity.ERROR,
        metadata={"offres_invalides": len(bad),
                  "exemples": "; ".join(f"{i}: {', '.join(r)}" for i, r in list(bad.items())[:5])})
