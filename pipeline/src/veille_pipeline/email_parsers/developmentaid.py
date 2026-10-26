"""Alertes DevelopmentAid (HTML) : liens /jobs/view/{id} et /tenders/view/{id}.

Les e-mails tronquent eux-mêmes certains champs (« Great Brit... ») et la mise en page varie :
on garde le titre et le lien, et la date limite ou l'organisation quand elles sont lisibles.
Mise en page constatée le 23/10/2026 : un tableau « Title & Job type | Company | Location | Deadline »
où « Company » n'est qu'un type d'organisme (« Multilateral organization ») et le titre est coupé
à 25 caractères ; l'ancienne mise en page (« Organisation: … Deadline: … ») reste lue en repli.
"""
import re
from datetime import datetime
from email.message import EmailMessage
from typing import Any

from selectolax.lexbor import LexborHTMLParser, LexborNode

_LINK = re.compile(r"developmentaid\.org/(jobs|tenders)/view/(\d+)")
_DEADLINE = re.compile(r"Deadline:\s*(\d{1,2} [A-Za-z]{3}),? (\d{4})")
_ROW_DEADLINE = re.compile(r"(\d{1,2} [A-Za-z]{3}),? (\d{4})")
_ORGANISATION = re.compile(r"Organisation:\s*(.+?)\s+(?:Deadline:|Sectors:|Type:)")


def _deadline(text: str, pattern: re.Pattern[str] = _DEADLINE) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%d %b %Y").date().isoformat()
    except ValueError:
        return None


def _row_cells(anchor: LexborNode) -> list[str] | None:
    """Cellules de la ligne du tableau qui contient le lien (titre, organisme, lieu, date limite)."""
    node = anchor.parent
    while node is not None:
        if node.tag == "tr":
            cells = [c for c in node.iter() if c.tag == "td"]
            if len(cells) >= 4:
                return [re.sub(r"\s+", " ", c.text(separator=" ", strip=True)) for c in cells]
        node = node.parent
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
        offer: dict[str, Any] = {
            "platform": "developmentaid", "job_id": job_id, "kind": kind,
            "title": title.rstrip(".… ") if truncated else title, "title_truncated": truncated,
            "organization": None, "deadline": None,
            "url": f"https://www.developmentaid.org/{kind}/view/{job_id}",
        }
        cells = _row_cells(anchor)
        if cells:
            offer["contract"] = cells[0].split(title, 1)[-1].strip() or None
            offer["organization_type"], offer["location"] = cells[1] or None, cells[2] or None
            offer["deadline"] = _deadline(cells[3], _ROW_DEADLINE)
        else:
            position = text.find(title)
            after = text[position + len(title): position + len(title) + 220] if position >= 0 else ""
            organisation = _ORGANISATION.search(after)
            offer["organization"] = organisation.group(1).rstrip(".… ") if organisation else None
            offer["deadline"] = _deadline(after)
        best[job_id] = offer
    return list(best.values())
