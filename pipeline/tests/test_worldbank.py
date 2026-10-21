import json
from datetime import date

from veille_pipeline.connectors.worldbank import WorldBankProcNoticesConnector
from veille_pipeline.normalizers.worldbank import normalize_worldbank

TODAY = date(2026, 10, 21)
SRC = {"id": "worldbank_procnotices_mdg", "config": {"keep_if": {"method_codes": ["INDV"]}}}


def _data(fixtures):
    return json.loads((fixtures / "worldbank/procnotices_mdg.json").read_text())


def test_keeps_only_open_individual_consultant_notices(fixtures):
    offers = WorldBankProcNoticesConnector().parse(_data(fixtures), SRC, TODAY)
    assert len(offers) == 4
    assert all(o.payload["procurement_method_code"] == "INDV" for o in offers)
    assert all(o.payload["submission_deadline_date"][:10] >= "2026-10-21" for o in offers)


def test_firms_can_be_enabled(fixtures):
    src = {"id": "x", "config": {"keep_if": {"method_codes": ["INDV", "CQS", "QCBS"]}}}
    assert len(WorldBankProcNoticesConnector().parse(_data(fixtures), src, TODAY)) > 4


def test_normalize(fixtures):
    raw = WorldBankProcNoticesConnector().parse(_data(fixtures), SRC, TODAY)[0]
    offer = normalize_worldbank(raw.payload, SRC)
    assert offer.contract_type == "consultancy" and offer.country == "Madagascar"
    assert offer.language == "fr" and offer.deadline >= TODAY and offer.posted_at
    assert "procurement-detail/" in (offer.canonical_url or "")
    assert "@" not in (offer.description or "")
