from pathlib import Path

import pytest

from veille_pipeline.embeddings import (
    FakeEmbedder,
    best_cv,
    cosine,
    get_embedder,
    offer_text,
    text_hash,
)
from veille_pipeline.scoring import (
    combine_scores,
    load_scoring_config,
    normalize_embed,
    score_offer,
)

CFG = load_scoring_config(Path(__file__).resolve().parents[2] / "config" / "scoring.yaml")

# textes factices : les vrais CV (cv/*.md) sont hors dépôt
FAKE_CVS = {
    "MEAL_EN": "monitoring evaluation learning survey baseline endline indicators evaluation",
    "DATA_FR": "données python tableau de bord base de données pipeline ingénieur data",
}


def test_offer_text_truncates_and_joins():
    text = offer_text("Titre", "Org", "mot " * 1000)
    assert text.startswith("Titre . Org .") and len(text) < 1600
    assert offer_text("T", None, None) == "T"


def test_fake_embedder_is_deterministic_and_normalized():
    e = FakeEmbedder()
    a, b = e.embed_cvs(["suivi évaluation"])[0], e.embed_offers(["suivi évaluation"])[0]
    assert a == b and cosine(a, b) == pytest.approx(1.0)


def test_best_cv_picks_closest_profile():
    e = FakeEmbedder()
    cvs = dict(zip(FAKE_CVS, e.embed_cvs(list(FAKE_CVS.values())), strict=True))
    meal = e.embed_offers(["Monitoring and Evaluation Specialist baseline survey"])[0]
    data = e.embed_offers(["Ingénieur data : pipeline python et base de données"])[0]
    assert best_cv(meal, cvs)[0] == "MEAL_EN"  # type: ignore[index]
    assert best_cv(data, cvs)[0] == "DATA_FR"  # type: ignore[index]
    assert best_cv(meal, {}) is None


def test_normalize_embed_bounds():
    assert normalize_embed(0.7, CFG) == 0.0
    assert normalize_embed(0.99, CFG) == 1.0
    assert normalize_embed(0.86, CFG) == pytest.approx(0.5)


def _score(**offer):
    base = {"title": "Monitoring and Evaluation Specialist", "description": "", "city": None,
            "country": "Madagascar", "remote": False, "language": "en", "contract_type": "cdi"}
    return score_offer({**base, **offer}, CFG)


def test_combine_without_cv_keeps_rule_score():
    s = _score()
    assert combine_scores(s, None, CFG) == s.final_score


def test_combine_is_weighted_average():
    s = _score()
    weight = CFG["embedding"]["weight"]
    expected = (1 - weight) * s.rule_normalized + weight * 1.0
    assert combine_scores(s, 0.99, CFG) == pytest.approx(expected)


def test_outside_zone_cap_survives_embeddings():
    s = _score(country="Ecuador")
    assert s.zone_cap is not None
    assert combine_scores(s, 0.99, CFG) <= s.zone_cap


def test_text_hash_changes_with_text():
    assert text_hash("a") != text_hash("b") and text_hash("a") == text_hash("a")


def test_get_embedder_fake(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "fake")
    assert isinstance(get_embedder(), FakeEmbedder)
