from datetime import date, timedelta
from typing import ClassVar

import httpx
import pytest

from veille_pipeline.digest import (
    DISCORD_LIMIT,
    due_follow_ups,
    render_digest,
    render_discord,
    send_discord,
    send_email,
    subject_for,
)

TODAY = date(2026, 10, 21)


def _offer(**kw):
    base = {"title": "Poste", "organization": "Org", "location_text": None, "country": None, "city": None,
            "remote": False, "contract_type": "unknown", "deadline": None, "canonical_url": "https://x.org/1",
            "final_score": 0.5, "recommended_cv": "DATA_FR", "matched_keywords": ["data"]}
    return {**base, **kw}


def test_zones_are_ordered_madagascar_first_whatever_the_scores():
    html = render_digest([
        _offer(title="Autre", final_score=0.9),
        _offer(title="Tana", country="Madagascar", final_score=0.3),
        _offer(title="Lille job", city="Lille", final_score=0.6),
    ], TODAY)
    assert html.index("Madagascar") < html.index("Lille") < html.index("Autres")


def test_long_titles_are_shortened_and_contract_is_readable():
    html = render_digest([_offer(title="x" * 300)], TODAY)
    assert "x" * 300 not in html and "…" in html
    assert "unknown" not in html and "contrat non précisé" in html


def test_subject_is_singular_for_one_offer():
    assert subject_for(1).endswith("1 offre") and subject_for(5).endswith("5 offres")


def test_titles_are_html_escaped():
    assert "<script>" not in render_digest([_offer(title="<script>alert(1)</script>")], TODAY)


# ── relances et Discord ───────────────────────────────────────────────────────



def _app(**kw):
    base = {"organization": "Org", "position": "Poste", "contact": None, "status": "applied",
            "sent_at": TODAY - timedelta(days=15), "follow_up_at": TODAY}
    return {**base, **kw}


def test_follow_ups_due_today_or_late_sorted_by_delay():
    apps = [
        _app(organization="B", follow_up_at=TODAY),
        _app(organization="A", follow_up_at=TODAY - timedelta(days=4)),
        _app(organization="Futur", follow_up_at=TODAY + timedelta(days=1)),
        _app(organization="Sans date", follow_up_at=None),
    ]
    due = due_follow_ups(apps, TODAY)
    assert [a["organization"] for a in due] == ["A", "B"]
    assert due[0]["overdue_days"] == 4


def test_closed_applications_are_not_followed_up():
    apps = [_app(status=s, organization=s) for s in ("rejected", "ghosted", "interview", "IGNORED")]
    assert due_follow_ups(apps, TODAY) == []
    assert len(due_follow_ups([_app(status=None)], TODAY)) == 1


def test_email_shows_follow_ups_even_without_new_offers():
    html = render_digest([], TODAY, due_follow_ups([_app(organization="Expertise France")], TODAY))
    assert "Relances à faire" in html and "Expertise France" in html
    assert "Rien de neuf" not in html
    assert "Relances à faire" not in render_digest([_offer()], TODAY)


def test_subject_mentions_follow_ups():
    assert subject_for(3, 2).endswith("3 offres, 2 relances")
    assert subject_for(0, 1).endswith("1 relance")


def test_discord_limits_to_ten_offers_best_first():
    offers = [_offer(title=f"Offre {i}", final_score=i / 100, canonical_url=f"https://x.org/{i}")
              for i in range(25)]
    text = render_discord(offers, TODAY)
    assert text.count("](<https://x.org/") == 10
    assert "Offre 24" in text and "Offre 14" not in text
    assert "… et 15 autres dans l'e-mail." in text


def test_discord_stays_under_the_2000_character_limit():
    offers = [_offer(title="T" * 300, organization="O" * 100, canonical_url="https://x.org/" + "u" * 200)
              for _ in range(10)]
    follow_ups = due_follow_ups([_app(organization="O" * 150, position="P" * 150)] * 5, TODAY)
    assert len(render_discord(offers, TODAY, follow_ups)) <= DISCORD_LIMIT


def test_discord_follow_ups_come_first_and_links_are_not_embedded():
    text = render_discord([_offer(country="Madagascar")], TODAY, due_follow_ups([_app()], TODAY))
    assert text.index("Relances à faire") < text.index("🇲🇬")
    assert "](<https://x.org/1>)" in text  # chevrons : pas d'aperçu de lien


def test_send_discord_posts_json_without_mentions(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json))
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    send_discord("https://discord.com/api/webhooks/1/x", "bonjour")
    assert calls == [("https://discord.com/api/webhooks/1/x",
                      {"content": "bonjour", "allowed_mentions": {"parse": []}})]


def test_send_discord_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, json, timeout: httpx.Response(
        404, request=httpx.Request("POST", url)))
    with pytest.raises(httpx.HTTPStatusError):
        send_discord("https://discord.com/api/webhooks/1/x", "x")


def test_interface_link_in_email_and_discord():
    url = "https://stagiaire.example.org/"
    assert f'href="{url}"' in render_digest([_offer()], TODAY, interface_url=url)
    assert "interface" not in render_digest([_offer()], TODAY).lower()
    text = render_discord([_offer()], TODAY, interface_url=url)
    assert text.endswith(f"Interface : <{url}>")


def test_discord_keeps_interface_link_under_the_limit():
    offers = [_offer(title="T" * 300, organization="O" * 100, canonical_url="https://x.org/" + "u" * 200)
              for _ in range(10)]
    follow_ups = due_follow_ups([_app(organization="O" * 150, position="P" * 150)] * 5, TODAY)
    text = render_discord(offers, TODAY, follow_ups, "https://stagiaire.example.org/")
    assert len(text) <= DISCORD_LIMIT and text.endswith("<https://stagiaire.example.org/>")


class _FakeSmtp:
    calls: ClassVar[list[tuple]] = []

    def __init__(self, host, port, timeout):
        self.calls.append(("connect", host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, msg):
        self.calls.append(("send", msg["From"], msg["To"]))


def test_send_email_plain_smtp_for_mailpit(monkeypatch):
    monkeypatch.setattr("veille_pipeline.digest.smtplib.SMTP", _FakeSmtp)
    _FakeSmtp.calls = []
    send_email("<p>x</p>", "Sujet", "moi@example.org", "mailpit", 1025)
    assert _FakeSmtp.calls == [("connect", "mailpit", 1025),
                               ("send", "stagiaire@localhost", "moi@example.org")]


def test_send_email_starttls_and_login_when_credentials(monkeypatch):
    monkeypatch.setattr("veille_pipeline.digest.smtplib.SMTP", _FakeSmtp)
    _FakeSmtp.calls = []
    send_email("<p>x</p>", "Sujet", "moi@example.org", "smtp.example.org", 587,
               user="bot@example.org", password="secret")
    assert _FakeSmtp.calls == [("connect", "smtp.example.org", 587), ("starttls",),
                               ("login", "bot@example.org"),
                               ("send", "bot@example.org", "moi@example.org")]
