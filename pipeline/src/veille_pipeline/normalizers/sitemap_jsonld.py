"""Normalisation d'un JobPosting schema.org (connecteur `sitemap_jsonld`)."""
from datetime import date, datetime

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import (
    _FR_WORDS,
    _REMOTE,
    canonicalize_url,
    detect_contract,
    html_to_text,
)

_CONTRACTS = {"training": "internship", "intern": "internship", "internship": "internship",
              "temporary": "cdd", "contractor": "consultancy", "volunteer": "volunteer"}


def _day(value: str | None) -> date | None:
    return datetime.fromisoformat(value).date() if value else None


def normalize_sitemap_jsonld(payload: dict, source: dict) -> Offer:
    defaults = source.get("config", {}).get("defaults", {})
    title = (payload.get("title") or "").strip()
    description = html_to_text(payload.get("description"))
    kinds = payload.get("employmentType") or []
    kinds = [kinds] if isinstance(kinds, str) else kinds
    contract = next((_CONTRACTS[k.lower()] for k in kinds if k.lower() in _CONTRACTS), None)
    locations = payload.get("jobLocation") or []
    place = (locations[0] if isinstance(locations, list) and locations else locations) or {}
    locality = ((place.get("address") or {}).get("addressLocality") or "") if isinstance(place, dict) else ""
    city = locality.split(",")[0].strip() or None
    posted = _day(payload.get("datePosted"))
    deadline = _day(payload.get("validThrough"))
    if deadline and posted and (deadline - posted).days > 400:
        deadline = None  # validThrough fictif (ex. +100 ans)
    hiring = payload.get("hiringOrganization") or {}
    sample = f"{title} {description or ''}"
    return Offer(
        canonical_url=canonicalize_url(payload.get("url")),
        title=title,
        organization=(hiring.get("name") if isinstance(hiring, dict) else None)
        or source.get("name"),
        location_text=locality or None,
        country=defaults.get("country"),
        city=city,
        remote=bool(_REMOTE.search(title)),
        contract_type=contract or detect_contract(title),
        language=defaults.get("language") or ("fr" if len(_FR_WORDS.findall(sample)) >= 3 else "en"),
        posted_at=posted,
        deadline=deadline,
        description=description,
    )
