"""Règles partagées entre pipeline et API : zone d'une offre, statuts, seuils de santé des sources."""
from typing import Any, Literal, get_args

from sqlalchemy import ColumnElement, case, func

# codes de zone (paramètre `region` de l'API) et libellés du rapport, dans l'ordre d'affichage
ZONES = {"mdg": "Madagascar", "lille": "Lille", "remote": "Télétravail / international",
         "other": "Autres"}

# une seule liste de statuts, pour les offres (user_status) comme pour les candidatures
Status = Literal["new", "interesting", "applied", "ghosted", "ignored", "rejected", "interview"]
STATUSES: tuple[str, ...] = get_args(Status)
# candidatures à ne plus relancer : refus, sans réponse définitif, entretien obtenu, écartée
CLOSED_STATUSES = frozenset({"ghosted", "ignored", "rejected", "interview"})

SILENT_AFTER_RUNS = 3  # passages sans nouvelle offre avant de signaler une source muette
FAILURES_ALERT = 3     # échecs consécutifs avant alerte


def zone_code(country: str | None, city: str | None, remote: bool | None) -> str:
    if country == "Madagascar":
        return "mdg"
    if (city or "").lower() == "lille":
        return "lille"
    return "remote" if remote else "other"


def zone_sql(country: Any, city: Any, remote: Any) -> ColumnElement[str]:
    """Même règle que `zone_code`, en SQL (filtre `region` de l'API)."""
    return case(
        (country == "Madagascar", "mdg"),
        (func.lower(city) == "lille", "lille"),
        (remote.is_(True), "remote"),
        else_="other",
    )
