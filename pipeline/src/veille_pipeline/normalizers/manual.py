"""Normalisation d'une offre ajoutée à la main (`POST /offers/manual`, commande `/offre`).

Les champs arrivent déjà structurés ; on complète seulement ce que la saisie a laissé vide.
"""
from datetime import date

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import _FR_WORDS, _REMOTE, canonicalize_url, detect_contract


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def normalize_manual(payload: dict, source: dict) -> Offer:
    title = (payload.get("title") or "").strip()
    description = payload.get("description")
    sample = f"{title} {description or ''}"
    contract = payload.get("contract_type") or "unknown"
    return Offer(
        # sans lien (texte collé), une URL interne stable : l'offre reste unique et dédoublonnable
        canonical_url=canonicalize_url(payload.get("url"))
        or f"urn:saisie-manuelle:{payload['external_id']}",
        title=title,
        organization=payload.get("organization"),
        location_text=payload.get("location_text"),
        country=payload.get("country"),
        city=payload.get("city"),
        remote=bool(payload.get("remote")) or bool(_REMOTE.search(title)),
        contract_type=detect_contract(sample) if contract == "unknown" else contract,
        language=payload.get("language") or ("fr" if len(_FR_WORDS.findall(sample)) >= 3 else "en"),
        posted_at=_day(payload.get("posted_at")),
        deadline=_day(payload.get("deadline")),
        description=description,
    )
