import dagster as dg
from db.models import Offer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.process import offers_deduped

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
