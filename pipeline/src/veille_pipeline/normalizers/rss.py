"""Normalisation d'une entrée RSS brute vers `Offer`."""
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from selectolax.lexbor import LexborHTMLParser

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.dates import find_deadline

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid"}
_FR_WORDS = re.compile(r"\b(le|la|les|des|pour|avec|dans|recrutement|appel|offre|poste)\b", re.IGNORECASE)
_REMOTE = re.compile(r"home[- ]based|remote|télétravail|teletravail", re.IGNORECASE)
_PLACES = {"antananarivo": "Antananarivo", "tana ": "Antananarivo", "lille": "Lille"}


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlparse(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k not in _TRACKING])
    path = parts.path.rstrip("/") or "/"
    return urlunparse((parts.scheme, parts.netloc.lower(), path, "", query, ""))


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    text = LexborHTMLParser(html).text(separator=" ")
    return re.sub(r"\s+", " ", text).strip() or None


def detect_contract(text: str) -> str:
    low = text.lower()
    if re.search(r"\b(stage|stagiaire|internship|intern)\b", low):
        return "internship"
    if re.search(r"consultan|expression of interest|ami\b|manifestation d'intér", low):
        return "consultancy"
    if re.search(r"\bcdi\b|permanent", low):
        return "cdi"
    if re.search(r"\bcdd\b|fixed[- ]term", low):
        return "cdd"
    if re.search(r"volunteer|volontaire|\bunv\b", low):
        return "volunteer"
    return "unknown"


def normalize_rss(payload: dict, source: dict) -> Offer:
    config = source.get("config", {})
    field_map = config.get("field_map", {})
    description = html_to_text(payload.get("content") or payload.get("summary"))
    title = (payload.get("title") or "").strip()
    text = f"{title} {description or ''} {payload.get('link') or ''}"
    low = text.lower()

    country = "Madagascar" if ("madagascar" in low or "antananarivo" in low) else None
    city = next((name for key, name in _PLACES.items() if key in low), None)
    if city == "Lille":
        country = country or "France"
    org_key = field_map.get("organization")
    posted = payload.get("published")
    return Offer(
        canonical_url=canonicalize_url(payload.get("link")),
        title=title,
        organization=payload.get(org_key) if org_key else None,
        location_text=city or country,
        country=country,
        city=city,
        remote=bool(_REMOTE.search(text)),
        contract_type=detect_contract(f"{title} {description or ''}"),
        language="fr" if len(_FR_WORDS.findall(text)) >= 2 else "en",
        posted_at=datetime.fromisoformat(posted).date() if posted else None,
        deadline=find_deadline(description or ""),
        description=description,
    )
