"""Alertes unvacancies.org (texte brut) : blocs « titre / organisation / grade · lieu · contrat / Closes … / lien »."""
import re
from datetime import date
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any

_JOB = re.compile(r"https://unvacancies\.org/jobs/([\w-]+)")
_CLOSES = re.compile(r"Closes (\d{1,2}) ([A-Z][a-z]{2})")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _deadline(line: str, sent: date | None) -> str | None:
    """« Closes 22 Oct » : l'année est celle de l'envoi, ou la suivante si le mois est déjà passé."""
    match = _CLOSES.search(line)
    if not match or sent is None or match.group(2) not in _MONTHS:
        return None
    month = _MONTHS.index(match.group(2)) + 1
    try:
        return date(sent.year + (month < sent.month), month, int(match.group(1))).isoformat()
    except ValueError:
        return None


def parse_unvacancies(msg: EmailMessage) -> list[dict[str, Any]]:
    body = msg.get_body(preferencelist=("plain",))
    if body is None:
        return []
    try:
        sent: date | None = parsedate_to_datetime(str(msg["Date"])).date()
    except (TypeError, ValueError):
        sent = None
    offers = []
    for block in re.split(r"\n\s*\n", body.get_content().replace("\r\n", "\n")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        match = _JOB.search(lines[-1]) if len(lines) >= 4 else None
        if not match:
            continue  # en-tête, liens de gestion de l'abonnement, pied de page
        details = [part.strip() for part in lines[2].split("·")]
        offers.append({
            "platform": "unvacancies", "job_id": match.group(1), "title": lines[0],
            "organization": lines[1],
            "grade": details[0] if len(details) == 3 else None,
            "location": details[-2] if len(details) >= 2 else None,
            "contract": details[-1],
            "deadline": _deadline(" ".join(lines[3:-1]), sent),
            # URL canonique : sans le paramètre `eid` qui identifie l'abonné
            "url": f"https://unvacancies.org/jobs/{match.group(1)}",
        })
    return offers
