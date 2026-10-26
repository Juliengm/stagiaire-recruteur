"""Normalisation d'une offre SmartRecruiters (liste + détail)."""
from datetime import datetime

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.dates import find_deadline
from veille_pipeline.normalizers.rss import canonicalize_url, detect_contract, html_to_text

_CONTRACTS = {"intern": "internship", "permanent": "cdi", "temporary": "cdd", "contract": "cdd",
              "volunteer": "volunteer"}


def normalize_smartrecruiters(payload: dict, source: dict) -> Offer:
    detail = payload.get("detail") or {}
    location = payload.get("location") or {}
    title = (payload.get("name") or "").strip()
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    description = html_to_text(" ".join(
        s.get("text") or "" for s in sections.values() if isinstance(s, dict) and s.get("text")))
    kind = (payload.get("typeOfEmployment") or {}).get("id")
    country = (location.get("country") or "").upper() or None
    released = payload.get("releasedDate")
    return Offer(
        canonical_url=canonicalize_url(detail.get("postingUrl")),
        title=title,
        organization=(payload.get("company") or {}).get("name") or source.get("name"),
        location_text=location.get("fullLocation"),
        country={"FR": "France"}.get(country or "", country),
        city=location.get("city") or None,
        remote=bool(location.get("remote")),
        contract_type=_CONTRACTS.get(kind or "") or detect_contract(title),
        language=(detail.get("language") or {}).get("code"),
        posted_at=datetime.fromisoformat(released).date() if released else None,
        deadline=find_deadline(description or ""),
        description=description,
    )
