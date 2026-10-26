from db.models import Source
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _seed(session: Session) -> None:
    session.add(Source(id="reliefweb_mdg", name="ReliefWeb", kind="reliefweb_api", priority=1,
                       config={"appname": "${RELIEFWEB_APPNAME}"}, region=["mdg"],
                       origin="yaml", user_fields=[]))
    session.commit()


def test_list_keeps_secret_placeholders(client: TestClient, session: Session) -> None:
    _seed(session)
    [src] = client.get("/sources").json()
    assert src["config"] == {"appname": "${RELIEFWEB_APPNAME}"} and src["origin"] == "yaml"


def test_patch_records_fields_edited_in_interface(client: TestClient, session: Session) -> None:
    _seed(session)
    r = client.patch("/sources/reliefweb_mdg", json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    r = client.patch("/sources/reliefweb_mdg", json={"priority": 2})
    assert r.json()["user_fields"] == ["enabled", "priority"]
    assert client.patch("/sources/reliefweb_mdg", json={"priority": 9}).status_code == 422
    assert client.patch("/sources/reliefweb_mdg", json={"enabled": None}).status_code == 422
    assert client.patch("/sources/nope", json={"enabled": True}).status_code == 404


def test_create_source(client: TestClient, session: Session) -> None:
    _seed(session)
    body = {"id": "ong_x", "name": "ONG X", "kind": "html_list", "region": ["lille"],
            "config": {"url": "https://ong-x.example/emplois"}}
    r = client.post("/sources", json=body)
    assert r.status_code == 201 and r.json()["origin"] == "api" and r.json()["enabled"] is True
    assert client.post("/sources", json=body).status_code == 409
    assert client.post("/sources", json={**body, "id": "y1", "kind": "cornerstone"}).status_code == 422
    assert client.post("/sources", json={**body, "id": "Pas Bon"}).status_code == 422
    assert client.post("/sources", json={**body, "id": "y2", "region": ["paris"]}).status_code == 422
    assert {s["id"] for s in client.get("/sources").json()} == {"reliefweb_mdg", "ong_x"}
