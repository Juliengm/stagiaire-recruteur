"""Normalisation d'une offre extraite d'une alerte e-mail."""
import re
from datetime import date

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import canonicalize_url, detect_contract

_FR_WORDS = re.compile(r"\b(le|la|les|des|pour|avec|dans|chargé|responsable|spécialiste|h/f|f/h)\b", re.IGNORECASE)
_REMOTE = re.compile(r"home[- ]?based|remote|télétravail", re.IGNORECASE)


def normalize_gmail_alert(payload: dict, source: dict) -> Offer:
    title = payload["title"].strip()
    location = (payload.get("location") or "").strip() or None
    low = f"{title} {location or ''}".lower()
    city = "Lille" if "lille" in low else ("Antananarivo" if "antananarivo" in low else None)
    country = (
        "Madagascar" if "madagascar" in low or city == "Antananarivo"
        else "France" if "france" in low or city == "Lille" else None
    )
    deadline = date.fromisoformat(payload["deadline"]) if payload.get("deadline") else None
    kind = payload.get("kind")
    return Offer(
        canonical_url=canonicalize_url(payload["url"]),
        title=title,
        organization=payload.get("organization"),
        location_text=location,
        country=country,
        city=city,
        remote=bool(_REMOTE.search(f"{title} {location or ''}")),
        contract_type="tender" if kind == "tenders" else detect_contract(f"{title} {payload.get('contract') or ''}"),
        language="fr" if len(_FR_WORDS.findall(title)) >= 1 else "en",
        deadline=deadline,
    )
