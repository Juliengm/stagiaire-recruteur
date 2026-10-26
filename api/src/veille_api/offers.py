"""Lecture et tri des offres : liste filtrable, statut choisi par Julien."""
from datetime import date, datetime
from typing import Annotated, Literal

from db.models import Offer, OfferScore, UserStatus
from db.rules import Status, zone_sql
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["offres"])

Region = Literal["mdg", "lille", "remote", "other"]


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
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OfferOut]:
    """Offres hors doublons, les mieux notées d'abord ; sans statut enregistré = « new »."""
    region_col = zone_sql(Offer.country, Offer.city, Offer.remote).label("region")
    status_col = func.coalesce(UserStatus.status, "new").label("status")
    stmt = (
        select(Offer, OfferScore, region_col, status_col, UserStatus.note)
        .outerjoin(OfferScore, OfferScore.offer_id == Offer.id)
        .outerjoin(UserStatus, UserStatus.offer_id == Offer.id)
        .where(Offer.duplicate_of.is_(None))
    )
    if status:
        stmt = stmt.where(status_col == status)
    if region:
        stmt = stmt.where(region_col == region)
    if min_score is not None:
        stmt = stmt.where(OfferScore.final_score >= min_score)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Offer.title.ilike(pattern), Offer.organization.ilike(pattern),
                              Offer.description.ilike(pattern)))
    stmt = stmt.order_by(OfferScore.final_score.desc().nulls_last(), Offer.id.desc())
    rows = session.execute(stmt.limit(limit).offset(offset)).all()
    return [
        OfferOut(
            id=o.id, title=o.title, organization=o.organization, location_text=o.location_text,
            region=reg, contract_type=o.contract_type, deadline=o.deadline,
            canonical_url=o.canonical_url, first_seen_at=o.first_seen_at,
            final_score=s.final_score if s else None,
            recommended_cv=s.recommended_cv if s else None,
            matched_keywords=(s.matched_keywords or []) if s else [],
            status=st, note=note,
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
    session.commit()
    return StatusOut(offer_id=offer_id, status=row.status, note=row.note, updated_at=row.updated_at)
