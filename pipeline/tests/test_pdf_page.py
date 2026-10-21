from datetime import date
from pathlib import Path

import httpx

from veille_pipeline.connectors.pdf_page import PdfPageConnector
from veille_pipeline.normalizers.dates import find_deadline
from veille_pipeline.normalizers.pdf_page import normalize_pdf_page
from veille_pipeline.sources_config import load_sources

SOURCES = {s["id"]: s for s in load_sources(Path(__file__).resolve().parents[2] / "sources.yaml")}
SEED = SOURCES["seed_madagascar"]


def _page(fixtures):
    return (fixtures / "html" / "seed_madagascar_jobs.html").read_text(encoding="utf8")


def test_find_pdf_links(fixtures):
    links = PdfPageConnector().find_links(_page(fixtures), SEED["config"]["url"], SEED["config"])
    assert len(links) == 5
    assert all("/download_file/" in url for url in links)
    assert "Head of Programmes" in links.values()  # « (PDF) » retiré du titre


def test_pdf_extraction_and_normalization(fixtures):
    content = (fixtures / "pdf" / "seed_financial_resilience.pdf").read_bytes()
    raw = PdfPageConnector().build(
        "seed_madagascar", "https://madagascar.co.uk/download_file/x/187",
        "Financial Resilience Officer", content)
    assert "Financial Resilience" in raw.payload["text"] and "\n" not in raw.payload["text"]
    offer = normalize_pdf_page(raw.payload, SEED)
    assert offer.title == "Financial Resilience Officer"
    assert offer.organization == "SEED Madagascar" and offer.country == "Madagascar"
    assert offer.deadline == date(2026, 10, 26)
    assert offer.language == "en" and offer.description


def test_find_deadline_variants():
    assert find_deadline("Application Deadline: Monday 26th October 2026 at 23:59 GMT") == date(2026, 10, 26)
    assert find_deadline("Date limite de dépôt : 3 novembre 2026") == date(2026, 11, 3)
    assert find_deadline("Clôture avant le 1er décembre 2026") == date(2026, 12, 1)
    assert find_deadline("rien ici") is None


class FakeHttp:
    def __init__(self, fixtures, known_pdf=b"%PDF-"):
        self.page = _page(fixtures)
        self.pdf = (fixtures / "pdf" / "seed_financial_resilience.pdf").read_bytes()
        self.calls: list[str] = []

    def allowed(self, url):
        return True

    def get(self, url):
        self.calls.append(url)
        if url.endswith("/jobs"):
            return httpx.Response(200, text=self.page)
        return httpx.Response(200, content=self.pdf)


def test_fetch_skips_known_pdfs(fixtures):
    http = FakeHttp(fixtures)
    links = list(PdfPageConnector().find_links(http.page, SEED["config"]["url"], SEED["config"]))
    source = {**SEED, "known_external_ids": links[:3]}
    offers = list(PdfPageConnector().fetch(source, None, http))  # type: ignore[arg-type]
    assert len(offers) == 2 and len(http.calls) == 3  # page + 2 PDF nouveaux
    assert {o.external_id for o in offers} == set(links[3:])


def test_non_pdf_response_is_ignored(fixtures):
    http = FakeHttp(fixtures)
    http.pdf = b"<html>login</html>"
    assert list(PdfPageConnector().fetch(SEED, None, http)) == []  # type: ignore[arg-type]
