from datetime import date

from veille_pipeline.connectors.csv_dataset import CsvDatasetConnector
from veille_pipeline.normalizers.csv_dataset import normalize_csv_dataset

SRC = {"id": "csp_hauts_de_france", "config": {"filter": {"departement": "59"}}}
TODAY = date(2026, 10, 20)


def _lines(fixtures):
    return (fixtures / "csv/csp_extrait.csv").read_text(encoding="utf-8").splitlines()


def test_keeps_only_nord_and_open_offers_once_per_reference(fixtures):
    offers = CsvDatasetConnector().parse(_lines(fixtures), SRC, TODAY)
    assert offers
    refs = [o.external_id for o in offers]
    assert len(refs) == len(set(refs))
    assert all("(59)" in o.payload["Localisation du poste"] for o in offers)
    assert all(o.url == f"https://choisirleservicepublic.gouv.fr/offre-emploi/{o.external_id}/" for o in offers)


def test_expired_offers_are_dropped(fixtures):
    assert CsvDatasetConnector().parse(_lines(fixtures), SRC, date(2030, 1, 1)) == []


def test_normalize(fixtures):
    raw = CsvDatasetConnector().parse(_lines(fixtures), SRC, TODAY)[0]
    offer = normalize_csv_dataset(raw.payload, SRC)
    assert offer.country == "France" and offer.language == "fr"
    assert offer.deadline is not None and offer.deadline >= TODAY
    assert offer.canonical_url and offer.title
