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
