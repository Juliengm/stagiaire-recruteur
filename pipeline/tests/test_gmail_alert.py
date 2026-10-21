import base64
from datetime import UTC, datetime
from email import message_from_bytes, policy

from veille_pipeline.connectors.gmail_alert import GmailAlertConnector
from veille_pipeline.email_parsers.developmentaid import parse_developmentaid
from veille_pipeline.email_parsers.linkedin import parse_linkedin
from veille_pipeline.normalizers.gmail_alert import normalize_gmail_alert

NOW = datetime(2026, 10, 21, tzinfo=UTC)
SOURCE = {
    "id": "email_alerts",
    "config": {
        "oauth_token_file": "fake", "label": "alertes-emploi", "processed_label": "traité",
        "parsers": {"linkedin": {"from_contains": "linkedin.com"},
                    "developmentaid": {"from_contains": "developmentaid.info"}},
    },
}


def _load(fixtures, name):
    return message_from_bytes((fixtures / "email" / name).read_bytes(), policy=policy.default)


def test_linkedin_blocks(fixtures):
    jobs = parse_linkedin(_load(fixtures, "linkedin_alert.anon.eml"))
    assert len(jobs) == 3
    first = jobs[0]
    assert first["title"] and first["organization"] and "Hauts-de-France" in first["location"]
    assert first["url"] == f"https://www.linkedin.com/jobs/view/{first['job_id']}/"
    assert all("trk" not in j["url"] and "Token" not in j["url"] for j in jobs)


def test_developmentaid_links_and_deadline(fixtures):
    jobs = parse_developmentaid(_load(fixtures, "developmentaid_alert.anon.eml"))
    assert len(jobs) == 6
    assert all(j["url"].startswith("https://www.developmentaid.org/jobs/view/") for j in jobs)
    assert jobs[0]["deadline"] == "2026-12-07"
    assert "?" not in jobs[0]["url"]


def test_normalize_linkedin_lille(fixtures):
    job = parse_linkedin(_load(fixtures, "linkedin_alert.anon.eml"))[0]
    offer = normalize_gmail_alert(job, SOURCE)
    assert offer.city == "Lille" and offer.country == "France"
    assert offer.canonical_url.startswith("https://www.linkedin.com/jobs/view/")


class _Exec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class FakeGmail:
    """Imite juste ce que le connecteur appelle ; enregistre les écritures."""

    def __init__(self, fixtures):
        raws = {"m1": "linkedin_alert.anon.eml", "m2": "developmentaid_alert.anon.eml"}
        self.raw = {i: base64.urlsafe_b64encode((fixtures / "email" / f).read_bytes()).decode()
                    for i, f in raws.items()}
        self.queries, self.modified, self.created = [], [], []

    def users(self):
        return self

    def messages(self):
        return self

    def labels(self):
        return self

    def list(self, **kw):
        if "q" in kw:
            self.queries.append(kw["q"])
            return _Exec({"messages": [{"id": i} for i in self.raw]})
        return _Exec({"labels": [{"name": "alertes-emploi", "id": "L1"}]})

    def get(self, userId, id, format):
        return _Exec({"raw": self.raw[id]})

    def create(self, userId, body):
        self.created.append(body["name"])
        return _Exec({"id": "L2"})

    def batchModify(self, userId, body):
        self.modified.append(body)
        return _Exec({})


def test_fetch_reads_only_the_label_and_marks_after_finalize(fixtures):
    fake = FakeGmail(fixtures)
    connector = GmailAlertConnector(service_factory=lambda _f: fake)
    offers = list(connector.fetch(SOURCE, None, http=None))  # type: ignore[arg-type]
    assert fake.queries == ["label:alertes-emploi -label:traité"]
    assert len(offers) == 9 and {o.external_id.split(":")[0] for o in offers} == {"linkedin", "developmentaid"}
    assert fake.modified == []  # rien n'est marqué tant que les offres ne sont pas en base
    assert connector.finalize(SOURCE) == 2
    assert fake.created == ["traité"] and fake.modified[0]["addLabelIds"] == ["L2"]
    assert connector.finalize(SOURCE) == 0  # idempotent


def test_missing_token_fails_loudly():
    import pytest
    with pytest.raises(RuntimeError, match="GMAIL_TOKEN_FILE"):
        GmailAlertConnector().fetch({"id": "x", "config": {}}, None, http=None)  # type: ignore[arg-type]


def test_developmentaid_keeps_truncated_titles_but_prefers_full_ones():
    from email.message import EmailMessage
    html = (
        '<a href="https://www.developmentaid.org/jobs/view/1/x">Especialista en Transform...</a>'
        '<a href="https://www.developmentaid.org/jobs/view/1/x">Especialista en Transformación Digital</a>'
        '<a href="https://www.developmentaid.org/jobs/view/2/y">Directeur/directrice, Div...</a>'
        '<a href="https://www.developmentaid.org/jobs/view/3/z">View</a>'
    )
    msg = EmailMessage()
    msg.set_content("x")
    msg.add_alternative(html, subtype="html")
    jobs = {j["job_id"]: j for j in parse_developmentaid(msg)}
    assert set(jobs) == {"1", "2"}
    assert jobs["1"]["title"] == "Especialista en Transformación Digital" and not jobs["1"]["title_truncated"]
    assert jobs["2"]["title"] == "Directeur/directrice, Div" and jobs["2"]["title_truncated"]
