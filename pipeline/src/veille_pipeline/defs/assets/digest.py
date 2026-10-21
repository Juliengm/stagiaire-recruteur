import os
from datetime import date

import dagster as dg
from db.models import Digest, Offer, OfferScore, UserStatus
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.common import SCORING_FILE
from veille_pipeline.defs.assets.process import offers_scored
from veille_pipeline.digest import render_digest, send_email, subject_for
from veille_pipeline.scoring import load_scoring_config


@dg.asset(key="rapport_du_stagiaire", deps=[offers_scored], group_name="rapport")
def rapport_du_stagiaire() -> dg.MaterializeResult:
    """Envoie les offres pertinentes, ouvertes et jamais envoyées dans un récapitulatif précédent."""
    threshold = load_scoring_config(SCORING_FILE)["threshold"]
    today = date.today()
    with Session(get_engine()) as session:
        already = select(func.unnest(Digest.offer_ids)).scalar_subquery()
        rows = session.execute(
            select(Offer, OfferScore)
            .join(OfferScore, OfferScore.offer_id == Offer.id)
            .outerjoin(UserStatus, UserStatus.offer_id == Offer.id)
            .where(
                Offer.duplicate_of.is_(None), OfferScore.final_score >= threshold,
                (Offer.deadline.is_(None)) | (Offer.deadline >= today),
                Offer.id.not_in(already),
                func.coalesce(UserStatus.status, "new") != "ignored",
            )
        ).all()
        offers = [
            {"id": o.id, "title": o.title, "organization": o.organization,
             "location_text": o.location_text, "country": o.country, "city": o.city,
             "remote": o.remote, "contract_type": o.contract_type, "deadline": o.deadline,
             "canonical_url": o.canonical_url, "final_score": s.final_score,
             "recommended_cv": s.recommended_cv, "matched_keywords": s.matched_keywords}
            for o, s in rows
        ]
        if not offers:
            return dg.MaterializeResult(metadata={"offres": 0, "envoyé": False})
        to = os.environ.get("DIGEST_TO") or os.environ["CONTACT_EMAIL"]
        send_email(render_digest(offers, today), subject_for(len(offers)), to,
                   os.environ.get("SMTP_HOST", "mailpit"), int(os.environ.get("SMTP_PORT", "1025")))
        session.add(Digest(channel="email", offer_ids=[o["id"] for o in offers]))
        session.commit()
    return dg.MaterializeResult(metadata={"offres": len(offers), "envoyé": True})
