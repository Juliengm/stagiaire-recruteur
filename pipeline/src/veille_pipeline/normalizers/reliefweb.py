"""Normalisation d'une offre ReliefWeb v2 vers `Offer`."""
import re
from datetime import datetime

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import canonicalize_url, detect_contract

_TYPE = {"job": None, "consultancy": "consultancy", "internship": "internship",
         "volunteer": "volunteer"}
# Formules explicites seulement : « remote » seul décrit souvent des zones isolées, et
# « home based for X nationals » n'est pas ouvert à tous les candidats.
_REMOTE = re.compile(
    r"home[- ]based(?! for)|fully remote|remote (position|work|role|job|contract|consult)|"
    r"work(ing)? remotely|\bremote\b[,)]|télétravail|teletravail",
    re.IGNORECASE,
)
_FR_WORDS = re.compile(r"\b(le|la|les|des|pour|avec|dans|recrutement|appel|offre|poste)\b", re.IGNORECASE)


def _names(fields: dict, key: str) -> list[str]:
    return [x["name"] for x in fields.get(key, []) if x.get("name")]


def _date(value: str | None):
    return datetime.fromisoformat(value).date() if value else None


def normalize_reliefweb(payload: dict, source: dict) -> Offer:
    title = payload["title"].strip()
    body = payload.get("body") or ""
    countries, cities = _names(payload, "country"), _names(payload, "city")
    type_name = (_names(payload, "type") or [""])[0].lower()
    contract = _TYPE.get(type_name) or detect_contract(f"{title} {body[:500]}")
    text = f"{title} {body}"
    dates = payload.get("date", {})
    return Offer(
        canonical_url=canonicalize_url(payload.get("url")),
        title=title,
        organization=next(iter(_names(payload, "source")), None),
        location_text=", ".join(cities + countries) or None,
        country=countries[0] if countries else None,
        city=cities[0] if cities else None,
        remote=bool(_REMOTE.search(f"{title} {body[:400]}")),  # début d'annonce : évite « remote monitoring »
        contract_type=contract,
        language="fr" if len(_FR_WORDS.findall(text)) >= 3 else "en",
        posted_at=_date(dates.get("created")),
        deadline=_date(dates.get("closing")),
        description=body or None,
    )
