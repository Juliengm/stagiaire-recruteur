import os
from datetime import date

import dagster as dg
import httpx
from db.models import Application, Digest, Offer, OfferScore, UserStatus
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.common import SCORING_FILE
from veille_pipeline.defs.assets.process import offers_scored
from veille_pipeline.digest import (
    due_follow_ups,
    render_digest,
    render_discord,
    send_discord,
    send_email,
    subject_for,
)
from veille_pipeline.scoring import load_scoring_config


@dg.asset(key="rapport_du_stagiaire", deps=[offers_scored], group_name="rapport")
def rapport_du_stagiaire(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
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
        follow_ups = due_follow_ups([
            {"organization": a.organization, "position": a.position, "contact": a.contact,
             "status": a.status, "sent_at": a.sent_at, "follow_up_at": a.follow_up_at}
            for a in session.scalars(select(Application))], today)
        if not offers and not follow_ups:
            return dg.MaterializeResult(metadata={"offres": 0, "relances": 0, "envoyé": False})
        to = os.environ.get("DIGEST_TO") or os.environ["CONTACT_EMAIL"]
        interface_url = os.environ.get("INTERFACE_URL") or None
        send_email(render_digest(offers, today, follow_ups, interface_url), subject_for(len(offers), len(follow_ups)),
                   to, os.environ.get("SMTP_HOST", "mailpit"), int(os.environ.get("SMTP_PORT", "1025")),
                   os.environ.get("SMTP_USER") or None, os.environ.get("SMTP_PASSWORD"),
                   os.environ.get("SMTP_FROM") or None)
        session.add(Digest(channel="email", offer_ids=[o["id"] for o in offers]))
        discord_url = os.environ.get("DISCORD_WEBHOOK_URL")
        if discord_url:  # l'e-mail est parti : un échec Discord ne doit pas annuler l'enregistrement
            try:
                send_discord(discord_url, render_discord(offers, today, follow_ups, interface_url))
            except httpx.HTTPError as exc:
                context.log.warning(f"envoi Discord échoué : {exc}")
        session.commit()
    return dg.MaterializeResult(metadata={
        "offres": len(offers), "relances": len(follow_ups), "envoyé": True,
        "discord": bool(discord_url)})
