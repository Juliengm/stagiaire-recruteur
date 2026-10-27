import os
from pathlib import Path

import dagster as dg
from db.models import (
    CvProfile,
    Offer,
    OfferEmbedding,
    OfferScore,
    OfferSource,
    RawOffer,
    Source,
    UserStatus,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_pipeline.cv_files import read_cv
from veille_pipeline.db import get_engine
from veille_pipeline.dedupe import Candidate, find_duplicates, fingerprint
from veille_pipeline.defs.assets.common import SCORING_FILE
from veille_pipeline.defs.assets.ingest import raw_offers
from veille_pipeline.embeddings import best_cv, get_embedder, offer_text, text_hash
from veille_pipeline.normalizers import NORMALIZERS
from veille_pipeline.scoring import combine_scores, load_scoring_config, score_offer

CV_DIR = Path(os.environ.get("CV_DIR", "/app/cv"))


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
            if src.kind == "manual":  # choisie par Julien : « ça sent bon », quel que soit le score
                status = insert(UserStatus).values(offer_id=offer_id, status="interesting")
                session.execute(status.on_conflict_do_update(
                    index_elements=[UserStatus.offer_id], set_={"status": "interesting"},
                    where=UserStatus.status == "new"))
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


@dg.asset(group_name="traitement")
def cv_embeddings(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Embeddings des CV listés sous `cvs:` de scoring.yaml ; recalculé seulement si le texte change.

    Sans CV, aucun embedding : le score reste celui des règles.
    """
    cfg = load_scoring_config(SCORING_FILE)
    files: dict[str, Path] = {}
    for code, pattern in cfg.get("cvs", {}).items():
        found = sorted(CV_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
        if found:
            files[code] = found[-1]  # plusieurs versions : la plus récente
        else:
            context.log.warning(f"CV {code} introuvable ({pattern} dans {CV_DIR})")
    if not files:
        context.log.warning("aucun CV : pas de score sémantique")
        return dg.MaterializeResult(metadata={"cv": 0, "recalculés": 0})
    computed = 0
    with Session(get_engine()) as session:
        known = {c.code: c for c in session.scalars(select(CvProfile))}
        texts = {code: read_cv(path) for code, path in files.items()}
        stale = [code for code, text in texts.items()
                 if code not in known or known[code].content_hash != text_hash(text)]
        if stale:
            vectors = get_embedder().embed_cvs([texts[code] for code in stale])
            for code, vector in zip(stale, vectors, strict=True):
                stmt = insert(CvProfile).values(
                    code=code, text_content=texts[code], content_hash=text_hash(texts[code]),
                    embedding=vector)
                session.execute(stmt.on_conflict_do_update(
                    index_elements=[CvProfile.code],
                    set_={"text_content": stmt.excluded.text_content,
                          "content_hash": stmt.excluded.content_hash,
                          "embedding": stmt.excluded.embedding, "updated_at": func.now()}))
                computed += 1
        for code in set(known) - set(files):  # CV retiré de la configuration
            session.delete(known[code])
        session.commit()
    return dg.MaterializeResult(metadata={"cv": len(files), "recalculés": computed})


@dg.asset(deps=[offers_deduped, cv_embeddings], group_name="traitement")
def offers_scored(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Score par règles (config/scoring.yaml) + similarité avec les CV ; recalculé à chaque exécution."""
    cfg = load_scoring_config(SCORING_FILE)
    count = embedded = 0
    with Session(get_engine()) as session:
        cvs = {c.code: [float(x) for x in c.embedding] for c in session.scalars(select(CvProfile))}
        offers = session.scalars(select(Offer).where(Offer.duplicate_of.is_(None))).all()
        vectors: dict[int, list[float]] = {}
        if cvs:  # embeddings d'offres : seulement pour les textes nouveaux ou modifiés
            stored = {e.offer_id: e for e in session.scalars(select(OfferEmbedding))}
            texts = {o.id: offer_text(o.title, o.organization, o.description) for o in offers}
            todo = [o.id for o in offers
                    if o.id not in stored or stored[o.id].text_hash != text_hash(texts[o.id])]
            if todo:
                embedder = get_embedder()
                for start in range(0, len(todo), 64):
                    batch = todo[start:start + 64]
                    for oid, vector in zip(
                            batch, embedder.embed_offers([texts[i] for i in batch]), strict=True):
                        ins = insert(OfferEmbedding).values(
                            offer_id=oid, text_hash=text_hash(texts[oid]), embedding=vector)
                        session.execute(ins.on_conflict_do_update(
                            index_elements=[OfferEmbedding.offer_id],
                            set_={"text_hash": ins.excluded.text_hash,
                                  "embedding": ins.excluded.embedding}))
                        vectors[oid] = vector
                        embedded += 1
            for oid, row in stored.items():
                vectors.setdefault(oid, [float(x) for x in row.embedding])
        for offer in offers:
            score = score_offer(
                {"title": offer.title, "description": offer.description, "city": offer.city,
                 "country": offer.country, "remote": offer.remote, "language": offer.language,
                 "contract_type": offer.contract_type}, cfg)
            nearest = best_cv(vectors[offer.id], cvs) if offer.id in vectors else None
            cosine_score = nearest[1] if nearest else None
            final = combine_scores(score, cosine_score, cfg)
            stmt = insert(OfferScore).values(
                offer_id=offer.id, rule_score=score.rule_score, final_score=final,
                recommended_cv=score.recommended_cv or (nearest[0] if nearest else None),
                matched_keywords=score.matched_keywords, embed_score=cosine_score,
                embed_cv=nearest[0] if nearest else None)
            session.execute(stmt.on_conflict_do_update(
                index_elements=[OfferScore.offer_id],
                set_={"rule_score": stmt.excluded.rule_score, "final_score": stmt.excluded.final_score,
                      "recommended_cv": stmt.excluded.recommended_cv,
                      "matched_keywords": stmt.excluded.matched_keywords,
                      "embed_score": stmt.excluded.embed_score, "embed_cv": stmt.excluded.embed_cv,
                      "scored_at": stmt.excluded.scored_at}))
            count += 1
        session.commit()
    return dg.MaterializeResult(
        metadata={"offres_scorées": count, "embeddings_calculés": embedded, "cv": len(cvs)})
