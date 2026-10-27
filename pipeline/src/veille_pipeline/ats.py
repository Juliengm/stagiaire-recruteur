"""Détection du système de suivi de candidatures (ATS) d'une page carrières, par signatures."""
import re

# (nom, motif cherché dans les URL de la page, les en-têtes et le HTML)
SIGNATURES: list[tuple[str, re.Pattern[str]]] = [
    ("workable", re.compile(r"apply\.workable\.com|workable\.com/api|whr\.workable", re.IGNORECASE)),
    ("smartrecruiters", re.compile(r"smartrecruiters\.com", re.IGNORECASE)),
    ("teamtailor", re.compile(r"teamtailor\.com|teamtailor-cdn|data-teamtailor", re.IGNORECASE)),
    ("workday", re.compile(r"myworkdayjobs\.com|myworkdaysite\.com", re.IGNORECASE)),
    ("lever", re.compile(r"jobs\.lever\.co", re.IGNORECASE)),
    ("greenhouse", re.compile(r"boards\.greenhouse\.io|greenhouse\.io/embed|job-boards\.greenhouse", re.IGNORECASE)),
    ("recruitee", re.compile(r"recruitee\.com", re.IGNORECASE)),
    ("gestmax", re.compile(r"gestmax\.fr|gestmax\.eu", re.IGNORECASE)),
    ("cornerstone", re.compile(r"csod\.com|cornerstoneondemand", re.IGNORECASE)),
    ("bamboohr", re.compile(r"bamboohr\.com/(jobs|careers)", re.IGNORECASE)),
    ("personio", re.compile(r"jobs\.personio\.(de|com)|personio\.com/xml", re.IGNORECASE)),
    ("breezy", re.compile(r"breezy\.hr", re.IGNORECASE)),
    ("jazzhr", re.compile(r"applytojob\.com|jazz\.co", re.IGNORECASE)),
    ("odoo", re.compile(r"/web/assets/|odoo", re.IGNORECASE)),
    ("wordpress", re.compile(r"wp-content|wp-json", re.IGNORECASE)),
]

# Données exploitables sans connecteur HTML, par ATS.
HINTS = {
    "teamtailor": "RSS : https://<site>/jobs.rss (kind: rss)",
    "workable": "API publique : https://apply.workable.com/api/v1/widget/accounts/<compte>",
    "smartrecruiters": "API publique : https://api.smartrecruiters.com/v1/companies/<id>/postings",
    "lever": "API publique : https://api.lever.co/v0/postings/<compte>?mode=json",
    "greenhouse": "API publique : https://boards-api.greenhouse.io/v1/boards/<compte>/jobs",
    "recruitee": "API publique : https://<compte>.recruitee.com/api/offers/",
    "personio": "XML : https://<compte>.jobs.personio.de/xml",
}


def detect_ats(url: str, html: str, headers: dict[str, str] | None = None) -> list[str]:
    """Noms d'ATS reconnus, du plus spécifique au plus générique (CMS en dernier)."""
    haystack = "\n".join([url, *(f"{k}: {v}" for k, v in (headers or {}).items()), html])
    return [name for name, pattern in SIGNATURES if pattern.search(haystack)]
