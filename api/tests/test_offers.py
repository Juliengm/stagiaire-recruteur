from datetime import UTC, date, datetime, timedelta

from db.models import Offer, OfferScore, Source, UserStatus
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _offer(session: Session, title: str, score: float | None = None, **kw: object) -> Offer:
    offer = Offer(title=title, canonical_url=f"https://ex.org/{title}", **kw)
    session.add(offer)
    session.flush()
    if score is not None:
        session.add(OfferScore(offer_id=offer.id, rule_score=score, final_score=score,
                               recommended_cv="NP5_FR", matched_keywords=["suivi-évaluation"]))
    return offer


def _seed(session: Session) -> dict[str, int]:
    mdg = _offer(session, "Chargé S&E", 0.6, organization="ONG A", country="Madagascar",
                 description="Suivi et évaluation de projets")
    lille = _offer(session, "Data analyst", 0.4, organization="Asso B", city="Lille")
    remote = _offer(session, "Consultant data", 0.2, organization="Agence C", remote=True)
    unscored = _offer(session, "Comptable", organization="D")
    dup = _offer(session, "Chargé S&E bis", 0.9, organization="ONG A", country="Madagascar",
                 duplicate_of=mdg.id)
    session.add(UserStatus(offer_id=lille.id, status="interesting"))
    session.commit()
    return {"mdg": mdg.id, "lille": lille.id, "remote": remote.id, "unscored": unscored.id,
            "dup": dup.id}


def test_list_excludes_duplicates_and_sorts_by_score(client: TestClient, session: Session) -> None:
    ids = _seed(session)
    body = client.get("/offers").json()
    assert [o["id"] for o in body] == [ids["mdg"], ids["lille"], ids["remote"], ids["unscored"]]
    first = body[0]
    assert first["region"] == "mdg" and first["recommended_cv"] == "NP5_FR"
    assert first["matched_keywords"] == ["suivi-évaluation"] and first["status"] == "new"
    assert body[-1]["final_score"] is None and body[-1]["region"] == "other"


def test_filters(client: TestClient, session: Session) -> None:
    ids = _seed(session)

    def got(**params: object) -> list[int]:
        return [o["id"] for o in client.get("/offers", params=params).json()]

    assert got(region="lille") == [ids["lille"]]
    assert got(region="remote") == [ids["remote"]]
    assert got(min_score=0.3) == [ids["mdg"], ids["lille"]]
    assert got(status="interesting") == [ids["lille"]]
    assert ids["lille"] not in got(status="new") and ids["mdg"] in got(status="new")
    assert got(q="évaluation") == [ids["mdg"]]  # description
    assert got(q="agence") == [ids["remote"]]   # organisation, sans casse
    assert client.get("/offers", params={"status": "nope"}).status_code == 422


def test_expired_offers_hidden_by_default(client: TestClient, session: Session) -> None:
    today = date.today()
    old = _offer(session, "Expirée", 0.9, deadline=today - timedelta(days=1))
    last_day = _offer(session, "Dernier jour", 0.5, deadline=today)
    session.commit()
    assert [o["id"] for o in client.get("/offers").json()] == [last_day.id]
    shown = client.get("/offers", params={"include_expired": True}).json()
    assert [o["id"] for o in shown] == [old.id, last_day.id]


def test_set_status_upserts_and_keeps_note(client: TestClient, session: Session) -> None:
    ids = _seed(session)
    r = client.patch(f"/offers/{ids['mdg']}/status", json={"status": "applied", "note": "envoyée"})
    assert r.status_code == 200 and r.json()["status"] == "applied"
    first_update = r.json()["updated_at"]
    r = client.patch(f"/offers/{ids['mdg']}/status", json={"status": "interview"})
    assert r.json()["note"] == "envoyée" and r.json()["updated_at"] >= first_update
    assert [o["status"] for o in client.get("/offers", params={"region": "mdg"}).json()] == ["interview"]


def test_set_status_errors(client: TestClient, session: Session) -> None:
    ids = _seed(session)
    assert client.patch("/offers/999999/status", json={"status": "applied"}).status_code == 404
    assert client.patch(f"/offers/{ids['mdg']}/status", json={"status": "maybe"}).status_code == 422


def test_health_sources(client: TestClient, session: Session) -> None:
    now = datetime.now(UTC)
    session.add_all([
        Source(id="ok", kind="rss", last_success_at=now),
        Source(id="broken", kind="html_list", consecutive_failures=3, last_error="HTTP 503"),
        Source(id="quiet", kind="rss", consecutive_empty_runs=2, config={"silent_after_runs": 2}),
    ])
    session.commit()
    body = {s["id"]: s for s in client.get("/health/sources").json()}
    assert body["ok"]["last_success_at"] and not body["ok"]["failing"] and not body["ok"]["silent"]
    assert body["broken"]["failing"] and body["broken"]["last_error"] == "HTTP 503"
    assert body["quiet"]["silent"] and body["quiet"]["consecutive_empty_runs"] == 2
