"""Score par règles (SPEC §3.4, sans embeddings en phase 1)."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Score:
    rule_score: float
    final_score: float
    recommended_cv: str | None
    matched_keywords: list[str]
    rule_normalized: float = 0.0      # rule_score ramené à [0, 1], avant plafond de zone
    zone_cap: float | None = None     # plafond hors zone, réappliqué après combinaison


def load_scoring_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def _count(word: str, text: str) -> int:
    return len(re.findall(rf"(?<!\w){re.escape(word)}(?!\w)", text))


def score_offer(offer: dict[str, Any], cfg: dict[str, Any]) -> Score:
    title = (offer.get("title") or "").lower()
    description = (offer.get("description") or "").lower()
    per_profile: dict[str, float] = {}
    matched: set[str] = set()
    title_weight = cfg.get("title_multiplier", 3)
    title_total = description_total = 0.0
    for profile, keywords in cfg["profiles"].items():
        in_title = in_description = 0.0
        for word, weight in keywords.items():
            title_hits, description_hit = _count(word, title), min(_count(word, description), 1)
            if title_hits or description_hit:
                matched.add(word)
            in_title += weight * title_hits * title_weight
            in_description += weight * description_hit
        per_profile[profile] = in_title + in_description  # sert au choix du CV
        title_total += in_title
        description_total += in_description

    # la description est souvent un texte commun à tout un projet : plafonnée, elle ne peut pas,
    # seule, faire passer une offre
    score = title_total + min(description_total, cfg.get("description_cap", 2))
    bonus = cfg["location_bonus"]
    place = f"{offer.get('city') or ''} {offer.get('country') or ''}".lower()
    for key in ("antananarivo", "madagascar", "lille"):
        if key in place:
            score += bonus[key]
    if offer.get("remote"):
        score += bonus["remote"]
    country = (offer.get("country") or "").lower()
    outside_cap = None
    if (
        country
        and not offer.get("remote")
        and country not in cfg.get("allowed_countries", [])
    ):
        score -= cfg.get("outside_zone_penalty", 0)
        outside_cap = cfg.get("outside_zone_cap")
    score += cfg["contract_bonus"].get(offer.get("contract_type") or "", 0)
    score -= 5 * sum(1 for word in cfg["excluded"] if _count(word, title))
    if offer.get("contract_type") == "internship":
        score -= 5

    normalized = max(0.0, min(score / cfg["rule_score_cap"], 1.0))
    if not matched:
        normalized = min(normalized, cfg.get("no_keyword_cap", 0.1))  # lieu seul : jamais pertinent
    if outside_cap is not None:
        normalized = min(normalized, outside_cap)
    candidates = _cv_candidates(per_profile, offer.get("language"))
    best = max(candidates, key=lambda p: per_profile[p]) if candidates else None
    return Score(
        rule_score=score,
        final_score=normalized,
        recommended_cv=best if best and per_profile[best] > 0 else None,
        matched_keywords=sorted(matched),
        rule_normalized=max(0.0, min(score / cfg["rule_score_cap"], 1.0)),
        zone_cap=outside_cap,
    )


def normalize_embed(cosine_score: float, cfg: dict[str, Any]) -> float:
    """Cosinus brut → [0, 1] : les cosinus e5 se concentrent entre 0,7 et 0,9."""
    floor, ceil = cfg["embedding"]["floor"], cfg["embedding"]["ceil"]
    return max(0.0, min((cosine_score - floor) / (ceil - floor), 1.0))


def combine_scores(score: Score, cosine_score: float | None, cfg: dict[str, Any]) -> float:
    """final = (1 - w) × règles + w × embeddings ; sans CV, le score par règles seul."""
    if cosine_score is None:
        return score.final_score
    weight = cfg["embedding"]["weight"]
    final = (1 - weight) * score.rule_normalized + weight * normalize_embed(cosine_score, cfg)
    return min(final, score.zone_cap) if score.zone_cap is not None else final


def _cv_candidates(per_profile: dict[str, float], language: str | None) -> list[str]:
    """CV dans la langue de l'offre (SPEC §3.7) : codes en `_FR` pour le français, `_EN` sinon."""
    suffix = "_FR" if language == "fr" else "_EN"
    matching = [p for p in per_profile if p.endswith(suffix)]
    best_matching = max((per_profile[p] for p in matching), default=0)
    return matching if best_matching > 0 else list(per_profile)  # repli : meilleur profil, toute langue
