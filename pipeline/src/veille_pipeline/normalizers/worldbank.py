"""Normalisation d'un avis de passation de marchés de la Banque mondiale."""
import re
from datetime import date, datetime

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import canonicalize_url, html_to_text

NOTICE_URL = "https://projects.worldbank.org/en/projects-operations/procurement-detail/{id}"
_METHOD_CONTRACT = {"INDV": "consultancy", "CQS": "tender", "QCBS": "tender", "QBS": "tender"}


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def normalize_worldbank(payload: dict, source: dict) -> Offer:
    title = re.sub(r"\s+", " ", payload["bid_description"]).strip()
    text = html_to_text(payload.get("notice_text"))
    country = payload.get("project_ctry_name")
    try:
        posted = datetime.strptime(payload.get("noticedate", ""), "%d-%b-%Y").date()
    except ValueError:
        posted = None
    project = " – ".join(filter(None, (payload.get("project_name"), payload.get("project_id"))))
    return Offer(
        canonical_url=canonicalize_url(NOTICE_URL.format(id=payload["id"])),
        title=title,
        organization=payload.get("contact_organization") or project or None,
        location_text=country,
        country=country if country == "Madagascar" else None,
        contract_type=_METHOD_CONTRACT.get(payload.get("procurement_method_code", ""), "consultancy"),
        language="fr" if payload.get("notice_lang_name") == "French" else "en",
        posted_at=posted,
        deadline=_parse_date(payload.get("submission_deadline_date")),
        description=" ".join(filter(None, (project, text))) or None,
    )
