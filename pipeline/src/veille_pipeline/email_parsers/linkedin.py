"""Alertes LinkedIn (texte brut) : blocs « titre / organisation / lieu / lien »."""
import re
from email.message import EmailMessage
from typing import Any

_VIEW = re.compile(r"(?:Voir l.offre d.emploi|View job)\s*:\s*(https://\S+)", re.IGNORECASE)
_JOB_ID = re.compile(r"/jobs/view/(\d+)")
_SEPARATOR = re.compile(r"\n-{20,}[ \t]*\n")


def parse_linkedin(msg: EmailMessage) -> list[dict[str, Any]]:
    body = msg.get_body(preferencelist=("plain",))
    if body is None:
        return []
    offers = []
    text = body.get_content().replace("\r\n", "\n")
    for block in _SEPARATOR.split(text):
        match = _VIEW.search(block)
        if not match:
            continue
        job_id = _JOB_ID.search(match.group(1))
        # Avant le lien : titre / organisation / lieu forment un paragraphe de 3 lignes ; les mentions
        # (« recrute activement », « 1 ancien élève ») et l'en-tête de l'e-mail sont sur 1-2 lignes.
        paragraphs = [
            [line.strip() for line in para.splitlines() if line.strip()]
            for para in re.split(r"\n\s*\n", block[: match.start()])
        ]
        job = [p for p in paragraphs if len(p) >= 3]
        if not job_id or not job:
            continue
        title, organization, location = job[-1][:3]
        offers.append({
            "platform": "linkedin", "job_id": job_id.group(1), "title": title,
            "organization": organization, "location": location,
            # URL canonique : sans le jeton de suivi personnel de l'e-mail
            "url": f"https://www.linkedin.com/jobs/view/{job_id.group(1)}/",
        })
    return offers
