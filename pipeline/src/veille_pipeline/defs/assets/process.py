import dagster as dg
from db.models import Offer, OfferScore, OfferSource, RawOffer, Source
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_pipeline.db import get_engine
from veille_pipeline.dedupe import Candidate, find_duplicates, fingerprint
from veille_pipeline.defs.assets.common import SCORING_FILE
from veille_pipeline.defs.assets.ingest import raw_offers
from veille_pipeline.normalizers import NORMALIZERS
from veille_pipeline.scoring import load_scoring_config, score_offer


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
                context.log.warning(
                    f"offre ignorée (titre ou URL manquant) : {raw.source_id}/{raw.external_id}")
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
    """Dédoublonnage : empreinte exacte puis similarité titre / organisation sur 60 jours."""
    marked = 0
    with Session(get_engine()) as session:
        offers = session.scalars(select(Offer).order_by(Offer.id)).all()
        duplicates = find_duplicates([
            Candidate(o.id, o.title, o.organization, o.posted_at or o.first_seen_at.date())
            for o in offers])
        for offer in offers:
            target = duplicates.get(offer.id)
            if offer.duplicate_of != target:
                offer.duplicate_of = target
                marked += 1
        session.commit()
        rate = len(duplicates) / len(offers) if offers else 0.0
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
                 "country": offer.country, "remote": offer.remote, "language": offer.language,
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
