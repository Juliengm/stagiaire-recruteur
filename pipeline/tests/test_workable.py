import json
from datetime import date
from pathlib import Path

from veille_pipeline.connectors.workable import WorkableConnector
from veille_pipeline.normalizers.workable import normalize_workable
from veille_pipeline.sources_config import load_sources

SOURCE = next(s for s in load_sources(Path(__file__).resolve().parents[2] / "sources.yaml")
              if s["id"] == "exotec")


def _data(fixtures):
    return json.loads((fixtures / "ats" / "workable_exotec.json").read_text(encoding="utf8"))


def test_countries_filter_keeps_france_only(fixtures):
    raws = WorkableConnector().parse(_data(fixtures), SOURCE)
    assert len(raws) == 6 and all(r.payload["country"] == "France" for r in raws)
    assert all(r.external_id and r.url.startswith("https://apply.workable.com/j/") for r in raws)


def test_normalize_lille_offer(fixtures):
    raws = WorkableConnector().parse(_data(fixtures), SOURCE)
    offers = [normalize_workable(r.payload, SOURCE) for r in raws]
    lille = [o for o in offers if o.city in ("Lille", "Wasquehal")]
    assert lille
    first = offers[0]
    assert first.organization == "Exotec" and first.country == "France"
    assert isinstance(first.posted_at, date) and first.description
    assert all(o.canonical_url and o.title for o in offers)


def test_no_filter_returns_everything(fixtures):
    source = {**SOURCE, "config": {"account": "exotec"}}
    assert len(WorkableConnector().parse(_data(fixtures), source)) == 8
