from pathlib import Path

import httpx
import pytest

from veille_pipeline.connectors import CONNECTORS
from veille_pipeline.connectors.html_list import HtmlListConnector
from veille_pipeline.normalizers.html_list import normalize_html_list
from veille_pipeline.sources_config import load_sources

SOURCES = {s["id"]: s for s in load_sources(Path(__file__).resolve().parents[2] / "sources.yaml")}


def _parse(fixtures, source_id, name):
    html = (fixtures / "html" / name).read_text(encoding="utf8")
    src = SOURCES[source_id]
    return src, HtmlListConnector().parse(html, src["config"]["url"], src)


def test_ngojobsinafrica_list(fixtures):
    src, raws = _parse(fixtures, "ngojobsinafrica_mdg", "ngojobsinafrica_madagascar.html")
    assert len(raws) == 10
    offers = [normalize_html_list(r.payload, src) for r in raws]
    first = offers[0]
    assert first.title == "Head of Programmes"
    assert first.organization == "SEED Madagascar"
    assert first.canonical_url == "https://ngojobsinafrica.com/job/head-of-programmes-80"
    assert str(first.posted_at) == "2026-10-14" and str(first.deadline) == "2026-10-27"
    assert first.country == "Madagascar"
    assert all(o.title and o.organization and o.deadline and o.deadline >= o.posted_at
               for o in offers)


def test_unvacancies_list(fixtures):
    src, raws = _parse(fixtures, "unvacancies_mdg_html", "unvacancies_madagascar.html")
    assert len(raws) == 19
    assert len({r.external_id for r in raws}) == 19
    offers = [normalize_html_list(r.payload, src) for r in raws]
    first = offers[0]
    assert first.title == "Chargé(e) de projet Education en Systeme Capacity Grant"
    assert first.organization == "UNESCO"
    assert first.location_text == "Antananarivo, Madagascar" and first.city == "Antananarivo"
    assert str(first.deadline) == "2026-11-06"
    assert first.canonical_url == (
        "https://unvacancies.org/jobs/charge-e-de-projet-education-en-systeme-capacity-grant-75424457")
    assert all(o.organization and o.deadline for o in offers)


class FakeHttp:
    def __init__(self, pages, allowed=True):
        self.pages, self.is_allowed, self.calls = pages, allowed, []

    def allowed(self, url):
        return self.is_allowed

    def get(self, url):
        self.calls.append(url)
        if url not in self.pages:
            raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url),
                                        response=httpx.Response(404))
        return httpx.Response(200, text=self.pages[url])


def test_pagination_stops_on_404(fixtures):
    src = SOURCES["ngojobsinafrica_mdg"]
    html = (fixtures / "html" / "ngojobsinafrica_madagascar.html").read_text(encoding="utf8")
    base = src["config"]["url"]
    http = FakeHttp({base: html, f"{base}page/2/": html.replace("-80/", "-81/")})
    offers = list(HtmlListConnector().fetch(src, None, http))  # type: ignore[arg-type]
    assert http.calls == [base, f"{base}page/2/", f"{base}page/3/"]
    assert len(offers) == 11  # 10 + 1 offre distincte de la page 2 (les autres sont déjà vues)


def test_robots_refusal_blocks_everything(fixtures):
    http = FakeHttp({}, allowed=False)
    with pytest.raises(PermissionError):
        list(HtmlListConnector().fetch(SOURCES["unvacancies_mdg_html"], None, http))  # type: ignore[arg-type]
    assert http.calls == []


def test_sources_without_selectors_are_not_ingestible():
    connector = CONNECTORS["html_list"]
    assert connector.is_configured(SOURCES["ngojobsinafrica_mdg"])  # type: ignore[attr-defined]
    assert not connector.is_configured(SOURCES["helvetas_jobs"])  # type: ignore[attr-defined]


def test_expertise_france_gestmax(fixtures):
    src, raws = _parse(fixtures, "expertise_france", "expertise_france_gestmax.html")
    assert len(raws) == 10 and len({r.external_id for r in raws}) == 10
    offers = [normalize_html_list(r.payload, src) for r in raws]
    first = offers[0]
    assert first.title == "Contracts and Procurement Assistant (M/W)"
    assert first.organization == "Expertise France"
    assert first.country == "Nigeria" and first.city == "Abuja"
    assert str(first.deadline) == "2026-11-06" and first.contract_type == "cdd"
    assert all(o.title and o.deadline and o.country for o in offers)
