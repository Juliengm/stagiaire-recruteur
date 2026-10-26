"""Base de test `veille_test` (Postgres du docker compose, publié en dev sur 127.0.0.1:5433).

URL : `VEILLE_TEST_DB_URL`, sinon construite depuis `.env` (POSTGRES_USER / POSTGRES_PASSWORD).
Pas de base joignable = échec franc, jamais de test sauté en silence.
"""
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from db.models import Base
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from veille_api.db import get_session
from veille_api.main import app

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _test_db_url() -> str:
    if url := os.environ.get("VEILLE_TEST_DB_URL"):
        return url
    env = dict(line.split("=", 1) for line in ENV_FILE.read_text().splitlines()
               if "=" in line and not line.lstrip().startswith("#"))
    return (f"postgresql+psycopg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
            "@127.0.0.1:5433/veille_test")


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = make_url(_test_db_url())
    assert url.database and url.database.endswith("_test"), "les tests vident la base : *_test seulement"
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine: Engine, session: Session) -> Iterator[TestClient]:
    def _session() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()
