from db.models import Offer, OfferScore, OfferSource, RawOffer, Source
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

OFFER = {"url": "https://jobs.example.org/42", "title": "Consultant S&E",
         "organization": "Projet X", "country": "Madagascar", "contract_type": "consultancy",
         "deadline": "2026-11-15", "description": "Appui au dispositif de suivi-évaluation.",
         "contact_email": "rh@example.org"}


def test_creates_disabled_source_and_raw_offer(client: TestClient, session: Session) -> None:
    resp = client.post("/offers/manual", json=OFFER)
    assert resp.status_code == 201 and resp.json()["created"] is True
    source = session.get_one(Source, "saisie_manuelle")
    assert source.kind == "manual" and source.enabled is False
    raw = session.get_one(RawOffer, resp.json()["raw_offer_id"])
    assert raw.payload["contact_email"] == "rh@example.org"
    assert raw.payload["external_id"] == resp.json()["external_id"]


def test_same_offer_twice_updates_instead_of_duplicating(client: TestClient,
                                                         session: Session) -> None:
    first = client.post("/offers/manual", json=OFFER).json()
    again = client.post("/offers/manual", json={**OFFER, "deadline": "2026-11-20"})
    assert again.status_code == 200 and again.json()["raw_offer_id"] == first["raw_offer_id"]
    assert len(session.scalars(select(RawOffer)).all()) == 1


def test_reports_offer_already_found_by_another_source(client: TestClient,
                                                       session: Session) -> None:
    session.add(Offer(canonical_url=OFFER["url"], title="Consultant S&E"))
    session.commit()
    offer_id = session.scalar(select(Offer.id))
    assert client.post("/offers/manual", json=OFFER).json()["offer_id"] == offer_id


def test_rejects_unknown_contract_and_empty_description(client: TestClient) -> None:
    assert client.post("/offers/manual", json={**OFFER, "contract_type": "freelance"}).status_code == 422
    assert client.post("/offers/manual", json={**OFFER, "description": ""}).status_code == 422


def test_state_is_404_until_processed_then_gives_score(client: TestClient,
                                                       session: Session) -> None:
    ext = client.post("/offers/manual", json=OFFER).json()["external_id"]
    assert client.get(f"/offers/manual/{ext}").status_code == 404
    offer = Offer(canonical_url=OFFER["url"], title="Consultant S&E")
    session.add(offer)
    session.flush()
    raw_id = session.scalar(select(RawOffer.id))
    session.add_all([OfferSource(offer_id=offer.id, raw_offer_id=raw_id),
                     OfferScore(offer_id=offer.id, final_score=0.4, recommended_cv="MEAL_FR")])
    session.commit()
    state = client.get(f"/offers/manual/{ext}").json()
    assert state == {"offer_id": offer.id, "duplicate_of": None, "final_score": 0.4,
                     "recommended_cv": "MEAL_FR"}


def test_offer_detail_uses_manual_contact_and_portal(client: TestClient,
                                                     session: Session) -> None:
    client.post("/offers/manual", json={**OFFER, "apply_url": "https://portail.example.org/42"})
    offer = Offer(canonical_url=OFFER["url"], title="Consultant S&E")
    session.add(offer)
    session.flush()
    session.add(OfferSource(offer_id=offer.id, raw_offer_id=session.scalar(select(RawOffer.id))))
    session.commit()
    body = client.get(f"/offers/{offer.id}").json()
    assert body["contact_emails"] == ["rh@example.org"]
    assert body["apply_url"] == "https://portail.example.org/42"
