import re
import unicodedata

import dagster as dg
from db.models import Offer, OfferScore, OfferSource, RawOffer, Source
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.common import SCORING_FILE
from veille_pipeline.defs.assets.ingest import raw_offers
from veille_pipeline.normalizers import NORMALIZERS
from veille_pipeline.scoring import load_scoring_config, score_offer


def fingerprint(title: str, organization: str | None) -> str:
    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+", " ", s).strip()

    return f"{norm(title)}|{norm(organization or '')}"


@dg.asset(deps=[raw_offers], group_name="traitement")
def offers_normalized(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Transforme les offres brutes pas encore traitées en `offers` (upsert sur l'URL canonique)."""
    created = skipped = 0
    with Session(get_engine()) as session:
        sources = {s.id: s for s in session.scalars(select(Source))}
        pending = session.execute(
            select(RawOffer)
            .outerjoin(OfferSource, OfferSource.raw_offer_id == RawOffer.id)
            .where(OfferSource.raw_offer_id.is_(None))
        ).scalars().all()
        for raw in pending:
            src = sources[raw.source_id]
            normalizer = NORMALIZERS.get(src.kind)
            if normalizer is None:
                skipped += 1
                continue
            offer = normalizer(raw.payload, {"config": src.config})
            if not offer.title or not offer.canonical_url:
                skipped += 1
                continue
            values = {**offer.model_dump(), "fingerprint": fingerprint(offer.title, offer.organization)}
            stmt = insert(Offer).values(**values)
            offer_id = session.execute(stmt.on_conflict_do_update(
                index_elements=[Offer.canonical_url], set_={"last_seen_at": func.now()}
            ).returning(Offer.id)).scalar_one()
            session.execute(insert(OfferSource).values(offer_id=offer_id, raw_offer_id=raw.id)
                            .on_conflict_do_nothing())
            created += 1
        session.commit()
    return dg.MaterializeResult(metadata={"traitées": created, "ignorées": skipped})


@dg.asset(deps=[offers_normalized], group_name="traitement")
def offers_deduped(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Dédoublonnage exact : même empreinte titre + organisation → `duplicate_of` la plus ancienne."""
    marked = 0
    with Session(get_engine()) as session:
        offers = session.scalars(select(Offer).order_by(Offer.id)).all()
        first: dict[str, int] = {}
        for offer in offers:
            if not offer.fingerprint:
                continue
            keeper = first.setdefault(offer.fingerprint, offer.id)
            target = None if keeper == offer.id else keeper
            if offer.duplicate_of != target:
                offer.duplicate_of = target
                marked += 1
        session.commit()
        duplicates = sum(1 for o in offers if o.duplicate_of)
        rate = duplicates / len(offers) if offers else 0.0
    return dg.MaterializeResult(metadata={"nouveaux_doublons": marked, "taux_doublons": rate})


@dg.asset(deps=[offers_deduped], group_name="traitement")
def offers_scored(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Score par règles (config/scoring.yaml) et CV recommandé ; recalculé à chaque exécution."""
    cfg = load_scoring_config(SCORING_FILE)
    count = 0
    with Session(get_engine()) as session:
        for offer in session.scalars(select(Offer).where(Offer.duplicate_of.is_(None))):
            score = score_offer(
                {"title": offer.title, "description": offer.description, "city": offer.city,
                 "country": offer.country, "remote": offer.remote,
                 "contract_type": offer.contract_type}, cfg)
            stmt = insert(OfferScore).values(
                offer_id=offer.id, rule_score=score.rule_score, final_score=score.final_score,
                recommended_cv=score.recommended_cv, matched_keywords=score.matched_keywords)
            session.execute(stmt.on_conflict_do_update(
                index_elements=[OfferScore.offer_id],
                set_={"rule_score": stmt.excluded.rule_score, "final_score": stmt.excluded.final_score,
                      "recommended_cv": stmt.excluded.recommended_cv,
                      "matched_keywords": stmt.excluded.matched_keywords, "scored_at": stmt.excluded.scored_at}))
            count += 1
        session.commit()
    return dg.MaterializeResult(metadata={"offres_scorées": count})
