import json

import pytest

from veille_pipeline.connectors.reliefweb import ReliefWebConnector
from veille_pipeline.normalizers.reliefweb import normalize_reliefweb


def _raw(fixtures, name):
    return ReliefWebConnector().parse(
        json.loads((fixtures / "reliefweb" / name).read_text()), "reliefweb_mdg"
    )


def test_parse_madagascar(fixtures):
    offers = _raw(fixtures, "jobs_mdg.json")
    assert len(offers) == 9
    assert all(o.external_id.isdigit() and o.url for o in offers)


def test_normalize_madagascar(fixtures):
    offers = [normalize_reliefweb(o.payload, {}) for o in _raw(fixtures, "jobs_mdg.json")]
    assert all(o.country == "Madagascar" and o.organization and o.deadline for o in offers)
    assert any(o.contract_type == "consultancy" for o in offers)
    assert any(o.city == "Antananarivo" for o in offers)


def test_remote_query_fixture_flags_remote(fixtures):
    offers = [normalize_reliefweb(o.payload, {}) for o in _raw(fixtures, "jobs_remote_me.json")]
    assert offers and any(o.remote for o in offers)


def test_missing_appname_fails_loudly():
    src = {"id": "x", "config": {"endpoint": "https://api.reliefweb.int/v2/jobs", "appname": "", "body": {}}}
    with pytest.raises(RuntimeError, match="appname"):
        ReliefWebConnector().fetch(src, None, http=None)  # type: ignore[arg-type]
