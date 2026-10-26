"""Normalisation d'une offre extraite d'une page HTML (connecteur `html_list`)."""
import re
from datetime import date, datetime

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import (
    _FR_WORDS,
    _PLACES,
    _REMOTE,
    canonicalize_url,
    detect_contract,
)

DEFAULT_DATE_FORMATS = ["%B %d, %Y", "%d %B %Y", "%d %b %Y", "%d/%m/%Y"]


def parse_date(value: str | None, formats: list[str]) -> date | None:
    if not value:
        return None
    value = value.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value[:10])
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def normalize_html_list(payload: dict, source: dict) -> Offer:
    config = source.get("config", {})
    defaults = config.get("defaults", {})
    formats = config.get("date_formats", DEFAULT_DATE_FORMATS)
    title = (payload.get("title") or "").strip()
    city_text, country_text = payload.get("city"), payload.get("country")
    location = payload.get("location") or ", ".join(p for p in (city_text, country_text) if p) or None
    text = f"{title} {location or ''} {payload.get('contract') or ''}"
    low = text.lower()
    country = (country_text or "").title() or defaults.get("country")
    if "madagascar" in low or "antananarivo" in low:
        country = "Madagascar"
    city = (city_text or "").title() or next(
        (name for key, name in _PLACES.items() if key in f"{low} "), None)
    return Offer(
        canonical_url=canonicalize_url(payload.get("url")),
        title=title,
        organization=payload.get("organization") or defaults.get("organization"),
        location_text=location or city or country,
        country=country,
        city=city,
        remote=bool(defaults.get("remote")) or bool(_REMOTE.search(text)),
        contract_type=detect_contract(text),
        language=defaults.get("language") or ("fr" if len(_FR_WORDS.findall(text)) >= 2 else "en"),
        posted_at=parse_date(payload.get("posted"), formats),
        deadline=parse_date(payload.get("deadline"), formats),
    )
