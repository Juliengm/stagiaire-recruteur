"""Lecture et tri des offres : liste filtrable, statut choisi par Julien."""
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

import yaml
from db.candidature import html_to_text
from db.models import (
    Application,
    ApplicationDraft,
    Offer,
    OfferScore,
    OfferSource,
    RawOffer,
    UserStatus,
)
from db.rules import Status, zone_code, zone_sql
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["offres"])

Region = Literal["mdg", "lille", "remote", "other"]

SCORING_FILE = Path(os.environ.get(
    "SCORING_FILE", Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"))


def score_threshold() -> float:
    """Seuil de `config/scoring.yaml`, le même que celui du récapitulatif."""
    return float(yaml.safe_load(SCORING_FILE.read_text())["threshold"])


class OfferOut(BaseModel):
    id: int
    title: str
    organization: str | None
    location_text: str | None
    region: str
    contract_type: str
    deadline: date | None
    canonical_url: str | None
    first_seen_at: datetime
    final_score: float | None
    recommended_cv: str | None
    matched_keywords: list[str]
    status: str
    note: str | None
    draft_id: int | None = None  # dossier de candidature en cours (vue Brouillons)


class OfferDetailOut(OfferOut):
    """Tout ce qu'il faut pour préparer une candidature (commande /candidatures)."""
    description: str | None
    language: str | None
    country: str | None
    city: str | None
    remote: bool
    posted_at: date | None
    contact_emails: list[str]  # saisis à la main, sinon repérés dans la description
    apply_url: str | None      # portail de candidature (saisie manuelle)
    application_ids: list[int]  # candidatures déjà enregistrées pour cette offre


EMAIL = re.compile(r"[\w.%+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.IGNORECASE)
OPEN_DRAFTS = ("draft", "deposited", "sent")  # un dossier abandonné n'en est plus un


def draft_is_empty(draft: ApplicationDraft) -> bool:
    """Dossier créé depuis l'interface et pas encore rédigé."""
    return not html_to_text(draft.email_html) and not html_to_text(draft.letter_html)


def offer_contacts(session: Session, offer: Offer) -> tuple[list[str], str | None]:
    """Adresses de candidature (saisies à la main, sinon repérées dans la description) et portail."""
    manual = [r.payload for r in session.scalars(
        select(RawOffer).join(OfferSource, OfferSource.raw_offer_id == RawOffer.id)
        .where(OfferSource.offer_id == offer.id, RawOffer.source_id == "saisie_manuelle"))]
    emails = [p["contact_email"] for p in manual if p.get("contact_email")]
    for found in EMAIL.findall(offer.description or ""):
        if found.lower() not in {e.lower() for e in emails}:
            emails.append(found)
    return emails, next((p["apply_url"] for p in manual if p.get("apply_url")), None)


class StatusIn(BaseModel):
    status: Status
    note: str | None = None


class StatusOut(BaseModel):
    offer_id: int
    status: str
    note: str | None
    updated_at: datetime


@router.get("/offers")
def list_offers(
    session: Annotated[Session, Depends(get_session)],
    status: Status | None = None,
    region: Region | None = None,
    min_score: float | None = None,
    q: str | None = None,
    include_expired: bool = False,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OfferOut]:
    """Offres hors doublons, les mieux notées d'abord ; sans statut enregistré = « new ».
    Les offres dont la date limite est passée sont masquées sauf `include_expired=true`.
    Sans `min_score`, les offres sans statut sous le seuil de scoring.yaml sont masquées ;
    `min_score=0` montre toutes les offres notées."""
    region_col = zone_sql(Offer.country, Offer.city, Offer.remote).label("region")
    status_col = func.coalesce(UserStatus.status, "new").label("status")
    stmt = (
        select(Offer, OfferScore, region_col, status_col, UserStatus.note)
        .outerjoin(OfferScore, OfferScore.offer_id == Offer.id)
        .outerjoin(UserStatus, UserStatus.offer_id == Offer.id)
        .where(Offer.duplicate_of.is_(None))
    )
    if not include_expired:
        stmt = stmt.where(or_(Offer.deadline.is_(None), Offer.deadline >= date.today()))
    if status:
        stmt = stmt.where(status_col == status)
    if region:
        stmt = stmt.where(region_col == region)
    if min_score is not None:
        stmt = stmt.where(OfferScore.final_score >= min_score)
    else:
        stmt = stmt.where(or_(status_col != "new", OfferScore.final_score >= score_threshold()))
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Offer.title.ilike(pattern), Offer.organization.ilike(pattern),
                              Offer.description.ilike(pattern)))
    stmt = stmt.order_by(OfferScore.final_score.desc().nulls_last(), Offer.id.desc())
    rows = session.execute(stmt.limit(limit).offset(offset)).all()
    drafts = dict(session.execute(
        select(ApplicationDraft.offer_id, func.max(ApplicationDraft.id))
        .where(ApplicationDraft.offer_id.in_([o.id for o, *_ in rows]),
               ApplicationDraft.status.in_(OPEN_DRAFTS))
        .group_by(ApplicationDraft.offer_id)).tuples().all())
    return [
        OfferOut(
            id=o.id, title=o.title, organization=o.organization, location_text=o.location_text,
            region=reg, contract_type=o.contract_type, deadline=o.deadline,
            canonical_url=o.canonical_url, first_seen_at=o.first_seen_at,
            final_score=s.final_score if s else None,
            recommended_cv=s.recommended_cv if s else None,
            matched_keywords=(s.matched_keywords or []) if s else [],
            status=st, note=note, draft_id=drafts.get(o.id),
        )
        for o, s, reg, st, note in rows
    ]


@router.patch("/offers/{offer_id}/status")
def set_status(offer_id: int, body: StatusIn,
               session: Annotated[Session, Depends(get_session)]) -> StatusOut:
    if session.get(Offer, offer_id) is None:
        raise HTTPException(404, "offre inconnue")
    values: dict[str, str | None] = {"status": body.status}
    if "note" in body.model_fields_set:  # note absente : on garde l'ancienne
        values["note"] = body.note
    stmt = insert(UserStatus).values(offer_id=offer_id, **values)
    stmt = stmt.on_conflict_do_update(index_elements=[UserStatus.offer_id],
                                      set_={**values, "updated_at": func.now()})
    row = session.execute(
        stmt.returning(UserStatus.status, UserStatus.note, UserStatus.updated_at)).one()
    if body.status in {"ignored", "rejected"}:  # offre écartée : son dossier vide n'a plus lieu d'être
        for draft in session.scalars(select(ApplicationDraft).where(
                ApplicationDraft.offer_id == offer_id, ApplicationDraft.status == "draft")):
            if draft_is_empty(draft):
                draft.status = "discarded"
    session.commit()
    return StatusOut(offer_id=offer_id, status=row.status, note=row.note, updated_at=row.updated_at)


@router.get("/offers/{offer_id}")
def get_offer(offer_id: int, session: Annotated[Session, Depends(get_session)]) -> OfferDetailOut:
    offer = session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(404, "offre inconnue")
    score = session.get(OfferScore, offer_id)
    status = session.get(UserStatus, offer_id)
    emails, apply_url = offer_contacts(session, offer)
    return OfferDetailOut(
        id=offer.id, title=offer.title, organization=offer.organization,
        location_text=offer.location_text,
        region=zone_code(offer.country, offer.city, offer.remote),
        contract_type=offer.contract_type, deadline=offer.deadline,
        canonical_url=offer.canonical_url, first_seen_at=offer.first_seen_at,
        final_score=score.final_score if score else None,
        recommended_cv=score.recommended_cv if score else None,
        matched_keywords=(score.matched_keywords or []) if score else [],
        status=status.status if status else "new", note=status.note if status else None,
        description=offer.description, language=offer.language, country=offer.country,
        city=offer.city, remote=offer.remote, posted_at=offer.posted_at,
        contact_emails=emails, apply_url=apply_url,
        draft_id=session.scalar(select(func.max(ApplicationDraft.id)).where(
            ApplicationDraft.offer_id == offer_id, ApplicationDraft.status.in_(OPEN_DRAFTS))),
        application_ids=list(session.scalars(
            select(Application.id).where(Application.offer_id == offer_id))),
    )
