from datetime import date

from veille_pipeline.digest import render_digest, subject_for

TODAY = date(2026, 10, 21)


def _offer(**kw):
    base = {"title": "Poste", "organization": "Org", "location_text": None, "country": None, "city": None,
            "remote": False, "contract_type": "unknown", "deadline": None, "canonical_url": "https://x.org/1",
            "final_score": 0.5, "recommended_cv": "DATA_FR", "matched_keywords": ["data"]}
    return {**base, **kw}


def test_zones_are_ordered_madagascar_first_whatever_the_scores():
    html = render_digest([
        _offer(title="Autre", final_score=0.9),
        _offer(title="Tana", country="Madagascar", final_score=0.3),
        _offer(title="Lille job", city="Lille", final_score=0.6),
    ], TODAY)
    assert html.index("Madagascar") < html.index("Lille") < html.index("Autres")


def test_long_titles_are_shortened_and_contract_is_readable():
    html = render_digest([_offer(title="x" * 300)], TODAY)
    assert "x" * 300 not in html and "…" in html
    assert "unknown" not in html and "contrat non précisé" in html


def test_subject_is_singular_for_one_offer():
    assert subject_for(1).endswith("1 offre") and subject_for(5).endswith("5 offres")


def test_titles_are_html_escaped():
    assert "<script>" not in render_digest([_offer(title="<script>alert(1)</script>")], TODAY)
