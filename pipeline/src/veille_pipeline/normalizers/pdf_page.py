"""Normalisation d'une offre publiée en PDF (connecteur `pdf_page`)."""
from veille_pipeline.models import Offer
from veille_pipeline.normalizers.dates import find_deadline
from veille_pipeline.normalizers.rss import _FR_WORDS, _REMOTE, canonicalize_url, detect_contract


def normalize_pdf_page(payload: dict, source: dict) -> Offer:
    config = source.get("config", {})
    defaults = config.get("defaults", {})
    title = (payload.get("title") or "").strip()
    text = payload.get("text") or ""
    sample = f"{title} {text[:3000]}"
    return Offer(
        canonical_url=canonicalize_url(payload.get("url")),
        title=title,
        organization=defaults.get("organization") or source.get("name"),
        location_text=defaults.get("country"),
        country=defaults.get("country"),
        remote=bool(_REMOTE.search(sample)),
        contract_type=detect_contract(sample),
        language=defaults.get("language") or ("fr" if len(_FR_WORDS.findall(sample)) >= 2 else "en"),
        deadline=find_deadline(text),
        description=text or None,
    )
