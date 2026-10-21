from veille_pipeline.connectors.rss import RssConnector
from veille_pipeline.normalizers.rss import canonicalize_url, normalize_rss
from veille_pipeline.scoring import load_scoring_config, score_offer

LESOPP = {"id": "lesopportunites_mdg", "config": {"url": "x"}}
UNVAC = {"id": "unvacancies_all", "config": {"url": "x", "field_map": {"organization": "category"}}}


def test_parse_unvacancies(fixtures):
    offers = RssConnector().parse((fixtures / "rss/unvacancies.xml").read_bytes(), UNVAC, "unvacancies_all")
    assert len(offers) == 50
    assert all(o.url and o.external_id and o.content_hash for o in offers)


def test_local_filter_keeps_only_matches(fixtures):
    src = {"id": "u", "config": {"local_filter": {"any_text": ["Madagascar"]}}}
    offers = RssConnector().parse((fixtures / "rss/unvacancies.xml").read_bytes(), src, "u")
    assert all("madagascar" in (o.payload["summary"] or "").lower() + o.payload["title"].lower() for o in offers)


def test_normalize_lesopportunites_madagascar(fixtures):
    raw = RssConnector().parse((fixtures / "rss/lesopp_pays.xml").read_bytes(), LESOPP, "lesopportunites_mdg")
    offers = [normalize_rss(r.payload, LESOPP) for r in raw]
    assert len(offers) == 10
    assert all(o.country == "Madagascar" and o.title for o in offers)
    assert all("utm_" not in (o.canonical_url or "") for o in offers)


def test_normalize_unvacancies_org_from_category(fixtures):
    raw = RssConnector().parse((fixtures / "rss/unvacancies.xml").read_bytes(), UNVAC, "unvacancies_all")
    offer = normalize_rss(raw[0].payload, UNVAC)
    assert offer.organization == "UNU"
    assert offer.posted_at is not None


def test_canonicalize_url_strips_tracking_and_trailing_slash():
    url = "https://Example.org/a/b/?utm_source=rss&id=3#frag"
    assert canonicalize_url(url) == "https://example.org/a/b?id=3"


def test_scoring_prefers_matching_profile_and_penalizes_internship():
    cfg = load_scoring_config(__import__("pathlib").Path(__file__).parents[2] / "config/scoring.yaml")
    good = score_offer({"title": "Monitoring and Evaluation Specialist (MEAL)", "description": "baseline survey",
                        "country": "Madagascar", "city": "Antananarivo", "contract_type": "cdd"}, cfg)
    intern = score_offer({"title": "Stage data", "description": "", "contract_type": "internship"}, cfg)
    assert good.recommended_cv == "MEAL_EN"
    assert good.final_score > 0.5
    assert intern.final_score == 0.0


def test_onsite_job_outside_zone_is_penalized():
    cfg = load_scoring_config(__import__("pathlib").Path(__file__).parents[2] / "config/scoring.yaml")
    base = {"title": "Monitoring Evaluation Lead", "description": "", "contract_type": "cdd"}
    abroad = score_offer({**base, "country": "Malawi", "remote": False}, cfg)
    home = score_offer({**base, "country": "Madagascar", "remote": False}, cfg)
    remote_abroad = score_offer({**base, "country": "Malawi", "remote": True}, cfg)
    assert abroad.final_score < 0.25 <= home.final_score
    assert remote_abroad.final_score >= 0.25


def _cfg():
    return load_scoring_config(__import__("pathlib").Path(__file__).parents[2] / "config/scoring.yaml")


def test_description_alone_cannot_qualify_an_offer():
    boilerplate = "suivi évaluation monitoring evaluation learning données data"
    offer = {"title": "Assistant en passation de marchés", "description": boilerplate,
             "country": "Madagascar", "contract_type": "consultancy", "language": "fr"}
    assert score_offer(offer, _cfg()).final_score < 0.25


def test_location_alone_is_never_relevant():
    offer = {"title": "Chauffeur", "description": "", "country": "Madagascar", "city": "Antananarivo",
             "contract_type": "consultancy"}
    assert score_offer({**offer, "title": "Responsable logistique"}, _cfg()).final_score <= 0.1


def test_cv_follows_offer_language():
    meal = {"title": "Monitoring and evaluation specialist", "description": "", "country": "Madagascar",
            "contract_type": "consultancy"}
    data = {**meal, "title": "Responsable plateforme de données", "language": "fr"}
    assert score_offer({**meal, "language": "en"}, _cfg()).recommended_cv == "MEAL_EN"
    assert score_offer(data, _cfg()).recommended_cv == "DATA_FR"
    # repli : une offre française qui ne parle que de S&E reçoit quand même un CV, pas None
    assert score_offer({**meal, "language": "fr"}, _cfg()).recommended_cv == "MEAL_EN"
