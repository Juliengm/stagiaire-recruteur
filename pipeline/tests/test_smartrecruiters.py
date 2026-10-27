import json
from pathlib import Path

import httpx

from veille_pipeline.connectors.smartrecruiters import SmartRecruitersConnector
from veille_pipeline.normalizers.smartrecruiters import normalize_smartrecruiters
from veille_pipeline.sources_config import load_sources

SOURCE = next(s for s in load_sources(Path(__file__).resolve().parents[2] / "sources.yaml")
              if s["id"] == "kiabi")


def _json(fixtures, name):
    return json.loads((fixtures / "ats" / name).read_text(encoding="utf8"))


def test_city_filter_keeps_lezennes_only(fixtures):
    raws = SmartRecruitersConnector().parse(_json(fixtures, "smartrecruiters_kiabi_list.json"), SOURCE)
    assert len(raws) == 3 and all(r.payload["location"]["city"] == "Lezennes" for r in raws)


def test_normalize_internship_with_detail(fixtures):
    detail = _json(fixtures, "smartrecruiters_kiabi_detail.json")
    payload = {**detail, "detail": detail}
    offer = normalize_smartrecruiters(payload, SOURCE)
    assert offer.contract_type == "internship"
    assert offer.city == "Lezennes" and offer.country == "France" and offer.language == "fr"
    assert offer.organization == "Kiabi"
    assert offer.canonical_url.startswith("https://jobs.smartrecruiters.com/KIABI/")
    assert offer.description and str(offer.posted_at) >= "2026-01-01"


class FakeHttp:
    def __init__(self, fixtures):
        self.list = _json(fixtures, "smartrecruiters_kiabi_list.json")
        self.detail = _json(fixtures, "smartrecruiters_kiabi_detail.json")
        self.calls: list[tuple[str, bool]] = []

    def get(self, url, check_robots=True):
        self.calls.append((url, check_robots))
        data = self.detail if "/postings/" in url else {**self.list, "totalFound": 6}
        return httpx.Response(200, json=data)


def test_fetch_respects_robots_and_skips_known_details(fixtures):
    http = FakeHttp(fixtures)
    known = ["744000156316739"]
    source = {**SOURCE, "known_external_ids": known}
    offers = list(SmartRecruitersConnector().fetch(source, None, http))  # type: ignore[arg-type]
    assert len(offers) == 3 and all(robots for _, robots in http.calls)
    detail_calls = [u for u, _ in http.calls if "/postings/" in u]
    assert len(detail_calls) == 2  # la première offre est déjà connue
    assert [o.external_id for o in offers if "detail" in o.payload] == [
        "744000155243344", "744000153203659"]
