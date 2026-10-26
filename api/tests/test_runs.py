import json
from collections.abc import Iterator

import httpx
import pytest
from db.models import Source
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from veille_api.main import app
from veille_api.runs import get_http


@pytest.fixture
def dagster(client: TestClient) -> Iterator[list[dict]]:
    """Faux Dagster : enregistre les requêtes GraphQL et accepte le lancement."""
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"launchRun": {
            "__typename": "LaunchRunSuccess", "run": {"runId": "abc123"}}}})

    app.dependency_overrides[get_http] = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    yield calls


def _seed(session: Session) -> None:
    session.add_all([Source(id="rss_a", kind="rss", enabled=True),
                     Source(id="off", kind="rss", enabled=False)])
    session.commit()


def test_launch_ingest_for_one_source(client: TestClient, session: Session,
                                      dagster: list[dict]) -> None:
    _seed(session)
    r = client.post("/runs", json={"job": "ingest", "source_id": "rss_a"})
    assert r.status_code == 201 and r.json()["run_id"] == "abc123"
    params = dagster[0]["variables"]["params"]
    assert params["selector"]["jobName"] == "ingest_job"
    assert params["executionMetadata"]["tags"] == [{"key": "dagster/partition", "value": "rss_a"}]


def test_launch_errors(client: TestClient, session: Session, dagster: list[dict]) -> None:
    _seed(session)
    assert client.post("/runs", json={"job": "ingest"}).status_code == 422
    assert client.post("/runs", json={"job": "ingest", "source_id": "nope"}).status_code == 404
    assert client.post("/runs", json={"job": "ingest", "source_id": "off"}).status_code == 409
    assert client.post("/runs", json={"job": "drop_db"}).status_code == 422
    assert dagster == []


def test_dagster_refusal_and_outage(client: TestClient, session: Session) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"launchRun": {
            "__typename": "PythonError", "message": "partition inconnue"}}})

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refusé")

    app.dependency_overrides[get_http] = lambda: httpx.Client(transport=httpx.MockTransport(refuse))
    r = client.post("/runs", json={"job": "registry"})
    assert r.status_code == 409 and "partition inconnue" in r.json()["detail"]
    app.dependency_overrides[get_http] = lambda: httpx.Client(transport=httpx.MockTransport(down))
    assert client.post("/runs", json={"job": "process"}).status_code == 502
