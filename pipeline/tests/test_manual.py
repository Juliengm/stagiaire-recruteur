from datetime import date

from veille_pipeline.normalizers import NORMALIZERS


def test_structured_fields_are_kept():
    offer = NORMALIZERS["manual"]({
        "external_id": "abc", "url": "https://jobs.example.org/42?utm_source=x",
        "title": "Consultant suivi-évaluation", "organization": "Projet X",
        "country": "Madagascar", "city": "Antananarivo", "contract_type": "consultancy",
        "language": "fr", "deadline": "2026-11-15", "description": "Appui au dispositif de S&E.",
    }, {"config": {}})
    assert offer.canonical_url == "https://jobs.example.org/42"
    assert offer.contract_type == "consultancy" and offer.deadline == date(2026, 11, 15)
    assert offer.country == "Madagascar" and offer.language == "fr"


def test_pasted_text_without_link_gets_internal_url_and_detections():
    offer = NORMALIZERS["manual"]({
        "external_id": "abc", "url": None, "title": "Remote M&E consultant",
        "contract_type": "unknown", "description": "Individual consultancy for an endline survey.",
    }, {"config": {}})
    assert offer.canonical_url == "urn:saisie-manuelle:abc"
    assert offer.remote and offer.contract_type == "consultancy" and offer.language == "en"
