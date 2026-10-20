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


def load_scoring_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def _count(word: str, text: str) -> int:
    return len(re.findall(rf"(?<!\w){re.escape(word)}(?!\w)", text))


def score_offer(offer: dict[str, Any], cfg: dict[str, Any]) -> Score:
    title = (offer.get("title") or "").lower()
    description = (offer.get("description") or "").lower()
    per_profile: dict[str, float] = {}
    matched: set[str] = set()
    for profile, keywords in cfg["profiles"].items():
        total = 0.0
        for word, weight in keywords.items():
            hits = _count(word, title) * 2 + min(_count(word, description), 1)
            if hits:
                total += weight * hits
                matched.add(word)
        per_profile[profile] = total

    score = sum(per_profile.values())
    bonus = cfg["location_bonus"]
    place = f"{offer.get('city') or ''} {offer.get('country') or ''}".lower()
    for key in ("antananarivo", "madagascar", "lille"):
        if key in place:
            score += bonus[key]
    if offer.get("remote"):
        score += bonus["remote"]
    score += cfg["contract_bonus"].get(offer.get("contract_type") or "", 0)
    score -= 5 * sum(1 for word in cfg["excluded"] if _count(word, title))
    if offer.get("contract_type") == "internship":
        score -= 5

    best = max(per_profile, key=lambda p: per_profile[p])
    normalized = max(0.0, min(score / cfg["rule_score_cap"], 1.0))
    return Score(
        rule_score=score,
        final_score=normalized,
        recommended_cv=best if per_profile[best] > 0 else None,
        matched_keywords=sorted(matched),
    )
