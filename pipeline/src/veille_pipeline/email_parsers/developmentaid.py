"""Alertes DevelopmentAid (HTML) : liens /jobs/view/{id} et /tenders/view/{id}.

Les e-mails tronquent eux-mêmes certains champs (« Great Brit... ») et la mise en page varie :
on garde le titre et le lien, et la date limite ou l'organisation quand elles sont lisibles.
"""
import re
from datetime import datetime
from email.message import EmailMessage
from typing import Any

from selectolax.lexbor import LexborHTMLParser

_LINK = re.compile(r"developmentaid\.org/(jobs|tenders)/view/(\d+)")
_DEADLINE = re.compile(r"Deadline:\s*(\d{1,2} [A-Za-z]{3}),? (\d{4})")
_ORGANISATION = re.compile(r"Organisation:\s*(.+?)\s+(?:Deadline:|Sectors:|Type:)")


def _deadline(text: str) -> str | None:
    match = _DEADLINE.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%d %b %Y").date().isoformat()
    except ValueError:
        return None


def parse_developmentaid(msg: EmailMessage) -> list[dict[str, Any]]:
    body = msg.get_body(preferencelist=("html",))
    if body is None:
        return []
    tree = LexborHTMLParser(body.get_content())
    text = re.sub(r"\s+", " ", tree.body.text(separator=" ")) if tree.body else ""
    best: dict[str, dict[str, Any]] = {}
    for anchor in tree.css("a"):
        match = _LINK.search(anchor.attributes.get("href") or "")
        title = anchor.text(strip=True)
        if not match or len(title) < 12:
            continue  # bouton ou lien d'en-tête
        kind, job_id = match.groups()
        truncated = title.endswith(("...", "…"))
        if job_id in best and (best[job_id]["title_truncated"] is False or truncated):
            continue  # on garde la version complète du titre si l'e-mail en donne une
        position = text.find(title)
        after = text[position + len(title): position + len(title) + 220] if position >= 0 else ""
        organisation = _ORGANISATION.search(after)
        best[job_id] = {
            "platform": "developmentaid", "job_id": job_id, "kind": kind,
            "title": title.rstrip(".… ") if truncated else title, "title_truncated": truncated,
            "organization": organisation.group(1).rstrip(".… ") if organisation else None,
            "deadline": _deadline(after),
            "url": f"https://www.developmentaid.org/{kind}/view/{job_id}",
        }
    return list(best.values())
