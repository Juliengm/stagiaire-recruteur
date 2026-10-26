from datetime import date
from pathlib import Path

import httpx

from veille_pipeline.connectors.sitemap_jsonld import (
    SitemapJsonLdConnector,
    job_posting,
    sitemap_urls,
)
from veille_pipeline.normalizers.sitemap_jsonld import normalize_sitemap_jsonld
from veille_pipeline.sources_config import load_sources

SOURCE = next(s for s in load_sources(Path(__file__).resolve().parents[2] / "sources.yaml")
              if s["id"] == "sopra_steria_lille")


def _read(fixtures, name):
    return (fixtures / "ats" / name).read_text(encoding="utf8")


def test_sitemap_filter_keeps_lille(fixtures):
    xml = _read(fixtures, "sopra_vacanciessitemap.xml")
    assert len(sitemap_urls(xml, None)) == 9
    urls = sitemap_urls(xml, SOURCE["config"]["url_filter"])
    assert len(urls) == 5 and all("-lille-in-" in u for u in urls)


def test_jsonld_internship_normalization(fixtures):
    posting = job_posting(_read(fixtures, "sopra_job_jid157.html"))
    assert posting is not None
    offer = normalize_sitemap_jsonld(posting, SOURCE)
    assert offer.title == "Stage Développeur/se Java Angular - Services Financiers - Lille"
    assert offer.contract_type == "internship"
    assert offer.organization == "Sopra Steria" and offer.country == "France"
    assert offer.city == "Villeneuve-d'Ascq" and offer.language == "fr"
    assert offer.posted_at == date(2026, 8, 27)
    assert offer.deadline is None  # validThrough fictif (2126)
    assert offer.canonical_url.endswith("jid-157") and offer.description


def test_page_without_jsonld():
    assert job_posting("<html><script type='application/ld+json'>{bad</script></html>") is None


class FakeHttp:
    def __init__(self, fixtures):
        self.sitemap = _read(fixtures, "sopra_vacanciessitemap.xml")
        self.page = _read(fixtures, ["ats", "sopra_job_jid157.html"][1])
        self.calls: list[str] = []

    def get(self, url):
        self.calls.append(url)
        if url.endswith(".xml"):
            return httpx.Response(200, content=self.sitemap.encode())
        return httpx.Response(200, text=self.page)


def test_fetch_downloads_only_new_filtered_pages(fixtures):
    http = FakeHttp(fixtures)
    known = sitemap_urls(http.sitemap, SOURCE["config"]["url_filter"])[:2]
    offers = list(SitemapJsonLdConnector().fetch(
        {**SOURCE, "known_external_ids": known}, None, http))  # type: ignore[arg-type]
    assert len(offers) == 3 and len(http.calls) == 4  # sitemap + 3 pages Lille inconnues
    assert all(o.external_id not in known and o.url == o.external_id for o in offers)
