"""Offres ajoutées à la main (commande `/offre` de Claude Code, ou tout client de l'API).

L'offre arrive déjà structurée. Elle est rangée comme offre brute d'une source « saisie
manuelle » (désactivée : jamais ingérée), puis normalisée, dédoublonnée et notée par le job
`process` comme les autres.
"""
import hashlib
from datetime import date
from typing import Annotated, Literal

from db.models import Offer, OfferScore, OfferSource, RawOffer, Source
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["offres"])

MANUAL_SOURCE = "saisie_manuelle"

Contract = Literal["cdi", "cdd", "consultancy", "roster", "volunteer", "internship", "tender",
                   "unknown"]


class ManualOfferIn(BaseModel):
    url: str | None = None            # page de l'offre ; absente pour un texte collé
    title: str = Field(min_length=3)
    organization: str | None = None
    location_text: str | None = None
    country: str | None = None        # en français, comme le reste de la base : Madagascar, France…
    city: str | None = None
    remote: bool = False
    contract_type: Contract = "unknown"
    language: Literal["fr", "en"] | None = None
    posted_at: date | None = None
    deadline: date | None = None
    description: str = Field(min_length=1)
    contact_email: str | None = None  # candidature par e-mail
    apply_url: str | None = None      # candidature par portail
    provenance: str | None = None     # lien, texte, pdf, gmail…


class ManualOfferOut(BaseModel):
    raw_offer_id: int
    external_id: str
    created: bool
    offer_id: int | None  # déjà en base sous la même URL (une autre source l'a trouvée)


def external_id(body: ManualOfferIn) -> str:
    key = body.url or f"{body.title}|{body.organization or ''}"
    return hashlib.sha256(key.strip().lower().encode()).hexdigest()[:16]


@router.post("/offers/manual", status_code=201)
def add_manual_offer(body: ManualOfferIn, response: Response,
                     session: Annotated[Session, Depends(get_session)]) -> ManualOfferOut:
    """Ajoute (ou met à jour) une offre saisie à la main ; lancer ensuite le job `process`."""
    session.execute(insert(Source).values(
        id=MANUAL_SOURCE, name="Saisie manuelle", kind="manual", config={}, region=[],
        enabled=False, origin="api").on_conflict_do_nothing())
    ext = external_id(body)
    payload = {**body.model_dump(mode="json"), "external_id": ext}
    blob = repr(sorted(payload.items())).encode()
    stmt = insert(RawOffer).values(source_id=MANUAL_SOURCE, external_id=ext, url=body.url,
                                   payload=payload, content_hash=hashlib.sha256(blob).hexdigest())
    known = session.scalar(select(RawOffer.id).where(
        RawOffer.source_id == MANUAL_SOURCE, RawOffer.external_id == ext))
    raw_id = session.execute(stmt.on_conflict_do_update(
        index_elements=[RawOffer.source_id, RawOffer.external_id],
        set_={"payload": stmt.excluded.payload, "content_hash": stmt.excluded.content_hash,
              "url": stmt.excluded.url},
    ).returning(RawOffer.id)).scalar_one()
    offer_id = session.scalar(select(Offer.id).where(Offer.canonical_url == body.url)) \
        if body.url else None
    session.commit()
    if known:
        response.status_code = 200
    return ManualOfferOut(raw_offer_id=raw_id, external_id=ext, created=known is None,
                          offer_id=offer_id)


class ManualOfferStateOut(BaseModel):
    offer_id: int
    duplicate_of: int | None
    final_score: float | None
    recommended_cv: str | None


@router.get("/offers/manual/{external_id}")
def manual_offer_state(external_id: str,
                       session: Annotated[Session, Depends(get_session)]) -> ManualOfferStateOut:
    """Où en est une offre saisie : 404 tant que le job `process` ne l'a pas notée."""
    row = session.execute(
        select(Offer.id, Offer.duplicate_of, OfferScore.final_score, OfferScore.recommended_cv)
        .join(OfferSource, OfferSource.offer_id == Offer.id)
        .join(RawOffer, RawOffer.id == OfferSource.raw_offer_id)
        .join(OfferScore, OfferScore.offer_id == Offer.id)
        .where(RawOffer.source_id == MANUAL_SOURCE, RawOffer.external_id == external_id)
    ).first()
    if row is None:
        raise HTTPException(404, "pas encore traitée (lancer le job process)")
    return ManualOfferStateOut(offer_id=row.id, duplicate_of=row.duplicate_of,
                               final_score=row.final_score, recommended_cv=row.recommended_cv)
