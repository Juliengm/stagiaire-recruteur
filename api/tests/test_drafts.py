import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from db.models import Application, Offer, UserStatus
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from veille_api.drafts import get_gmail
from veille_api.main import app

SRC = Path(__file__).resolve().parents[1] / "src"
LETTER = ("<p>Julien</p><p style=\"text-align: right\">ONG A</p>"
          "<p>Candidature au poste de Chargé S&amp;E chez ONG A : 10 ans d'expérience, 33 pays.</p>")


class FakeGmail:
    def __init__(self) -> None:
        self.saved: list[tuple[str, str | None]] = []
        self.threads: dict[str, tuple[str, date | None]] = {}

    def account(self) -> str:
        return "moi@example.org"

    def save_draft(self, raw: str, draft_id: str | None) -> tuple[str, str]:
        self.saved.append((raw, draft_id))
        return draft_id or f"r-{len(self.saved)}", "t-1"

    def thread_state(self, thread_id: str) -> tuple[str, date | None]:
        return self.threads.get(thread_id, ("pending", None))


@pytest.fixture
def gmail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGmail]:
    (tmp_path / "pdf").mkdir()
    import weasyprint
    weasyprint.HTML(string="<p>CV fictif : 10 ans, 33 pays.</p>").write_pdf(tmp_path / "pdf" / "CV_A.pdf")
    (tmp_path / "faits.md").write_text("10 ans d'expérience, 33 pays.", encoding="utf8")
    (tmp_path / "interdits.txt").write_text("# test\nmotinterdit\n", encoding="utf8")
    monkeypatch.setenv("CV_DIR", str(tmp_path))
    monkeypatch.setenv("CANDIDATURES_FROM", "moi@example.org")
    fake = FakeGmail()
    app.dependency_overrides[get_gmail] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_gmail, None)


def _draft(client: TestClient, session: Session, **kw: object) -> dict:
    offer = session.scalar(select(Offer)) or Offer(
        title="Chargé S&E", canonical_url="https://ex.org/1", organization="ONG A")
    session.add(offer)
    session.commit()
    body = {"offer_id": offer.id, "organization": "ONG A", "position": "Chargé S&E",
            "cv_file": "CV_A.pdf", "recipient": "rh@example.org", "subject": "Candidature — Chargé S&E",
            "email_html": "<p>Bonjour,</p><script>alert(1)</script>", "letter_html": LETTER,
            "letter_filename": "LM_Julien_Gasser_Morlay_ONG_A.pdf", **kw}
    resp = client.post("/drafts", json=body)
    assert resp.status_code == 201
    return resp.json()


def test_the_api_cannot_send_mail() -> None:
    code = "\n".join(p.read_text(encoding="utf8") for p in SRC.rglob("*.py"))
    assert not re.search(r"\.send\(|messages\(\)", code)  # brouillons et fils seulement


def test_html_is_sanitized_and_alignment_kept(client: TestClient, session: Session, gmail: FakeGmail) -> None:
    draft = _draft(client, session)
    assert "script" not in draft["email_html"]
    assert 'style="text-align:right"' in draft["letter_html"]


def test_cvs_listed_and_unknown_cv_refused(client: TestClient, session: Session, gmail: FakeGmail) -> None:
    assert client.get("/cvs").json() == ["CV_A.pdf"]
    assert client.get("/cvs/..%2Ffaits.md").status_code in {404, 422}
    draft = _draft(client, session)
    assert client.patch(f"/drafts/{draft['id']}", json={"cv_file": "autre.pdf"}).status_code == 422


def test_letter_preview_is_a_pdf(client: TestClient, session: Session, gmail: FakeGmail) -> None:
    draft = _draft(client, session)
    resp = client.get(f"/drafts/{draft['id']}/letter.pdf")
    assert resp.status_code == 200 and resp.content.startswith(b"%PDF")


def test_deposit_creates_gmail_draft_and_application(client: TestClient, session: Session,
                                                     gmail: FakeGmail) -> None:
    draft = _draft(client, session)
    resp = client.post(f"/drafts/{draft['id']}/deposit", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["draft"]["status"] == "deposited" and resp.json()["warnings"] == []
    app_row = session.scalar(select(Application))
    assert app_row is not None and app_row.draft_id == draft["id"] and app_row.status == "new"
    # modification puis nouveau dépôt : même brouillon Gmail remplacé, pas de seconde candidature
    edited = client.patch(f"/drafts/{draft['id']}", json={"subject": "Candidature — Chargé S&E — Julien"})
    assert edited.json()["stale"] is True
    client.post(f"/drafts/{draft['id']}/deposit", json={})
    assert [d for _, d in gmail.saved] == [None, "r-1"]
    assert len(session.scalars(select(Application)).all()) == 1


def test_forbidden_term_blocks_and_warnings_need_force(client: TestClient, session: Session,
                                                       gmail: FakeGmail) -> None:
    bad = _draft(client, session, email_html="<p>Le MotInterdit vous salue</p>")
    resp = client.post(f"/drafts/{bad['id']}/deposit", json={"force": True})
    assert resp.status_code == 422 and resp.json()["detail"]["blocking"]
    doubtful = _draft(client, session, letter_html=LETTER + "<p>Et 45 000 ménages.</p>")
    resp = client.post(f"/drafts/{doubtful['id']}/deposit", json={})
    assert resp.status_code == 422 and "45000" in str(resp.json()["detail"]["warnings"])
    assert client.post(f"/drafts/{doubtful['id']}/deposit", json={"force": True}).status_code == 200
    assert len(gmail.saved) == 1


def test_portal_draft_cannot_be_deposited(client: TestClient, session: Session, gmail: FakeGmail) -> None:
    draft = _draft(client, session, recipient=None, apply_url="https://portail.example.org")
    assert client.post(f"/drafts/{draft['id']}/deposit", json={}).status_code == 409


def test_sync_marks_sent_and_discarded(client: TestClient, session: Session, gmail: FakeGmail) -> None:
    draft = _draft(client, session)
    client.post(f"/drafts/{draft['id']}/deposit", json={})
    gmail.threads["t-1"] = ("sent", date(2026, 11, 2))
    assert client.post("/drafts/sync").json() == {"sent": 1, "discarded": 0}
    app_row = session.scalars(select(Application).execution_options(populate_existing=True)).one()
    assert app_row.status == "applied" and app_row.follow_up_at == date(2026, 11, 12)
    assert session.get_one(UserStatus, draft["offer_id"]).status == "applied"
    assert client.post(f"/drafts/{draft['id']}/deposit", json={}).status_code == 409
    other = _draft(client, session)
    client.post(f"/drafts/{other['id']}/deposit", json={})
    gmail.threads["t-1"] = ("missing", None)  # le fil du second brouillon a disparu
    assert client.post("/drafts/sync").json() == {"sent": 0, "discarded": 1}
