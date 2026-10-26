"""Normalisation d'une offre Workable (widget public)."""
from datetime import date

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.dates import find_deadline
from veille_pipeline.normalizers.rss import (
    _FR_WORDS,
    canonicalize_url,
    detect_contract,
    html_to_text,
)


def normalize_workable(payload: dict, source: dict) -> Offer:
    title = (payload.get("title") or "").strip()
    description = html_to_text(payload.get("description"))
    country, city = payload.get("country") or None, payload.get("city") or None
    published = payload.get("published_on")
    sample = f"{title} {payload.get('employment_type') or ''}"
    return Offer(
        canonical_url=canonicalize_url(payload.get("url")),
        title=title,
        organization=payload.get("company") or source.get("name"),
        location_text=", ".join(p for p in (city, country) if p) or None,
        country=country,
        city=city,
        remote=bool(payload.get("telecommuting")),
        contract_type=detect_contract(sample),
        language="fr" if len(_FR_WORDS.findall(f"{title} {description or ''}")) >= 3 else "en",
        posted_at=date.fromisoformat(published) if published else None,
        deadline=find_deadline(description or ""),
        description=description,
    )
