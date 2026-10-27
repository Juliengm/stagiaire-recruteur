"""Règles partagées entre pipeline et API : zone d'une offre, statuts, seuils de santé des sources."""
import unicodedata
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

# connecteurs écrits (clés de veille_pipeline.connectors.CONNECTORS, vérifié par un test) :
# seuls types acceptés pour une source ajoutée depuis l'interface
CONNECTOR_KINDS = frozenset({
    "rss", "csv_dataset", "reliefweb_api", "worldbank_procnotices", "gmail_alert", "html_list",
    "pdf_page", "workable", "smartrecruiters", "sitemap_jsonld",
})

SILENT_AFTER_RUNS = 3  # passages sans nouvelle offre avant de signaler une source muette
FAILURES_ALERT = 3     # échecs consécutifs avant alerte


# zone « Lille » : la métropole (MEL), pas seulement la ville ; noms normalisés par `_commune`
LILLE_METRO = frozenset({
    "lille", "lomme", "hellemmes", "villeneuve d'ascq", "roubaix", "tourcoing", "marcq en baroeul",
    "lambersart", "la madeleine", "wasquehal", "croix", "mons en baroeul", "loos", "ronchin",
    "faches thumesnil", "lezennes", "lesquin", "haubourdin", "wattrelos", "marquette lez lille",
    "saint andre lez lille", "hem", "seclin", "wambrechies", "mouvaux", "bondues", "armentieres",
    "halluin", "englos", "sequedin", "lys lez lannoy", "leers", "neuville en ferrain",
})


def _commune(city: str | None) -> str:
    """« Villeneuve-d’Ascq » → « villeneuve d'ascq » (casse, tirets, apostrophes, accents)."""
    s = (city or "").replace("œ", "oe").replace("Œ", "oe").replace("’", "'")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").split())


def is_lille(city: str | None) -> bool:
    return _commune(city) in LILLE_METRO


def zone_code(country: str | None, city: str | None, remote: bool | None) -> str:
    if country == "Madagascar":
        return "mdg"
    if is_lille(city):
        return "lille"
    return "remote" if remote else "other"


def _commune_sql(city: Any) -> ColumnElement[str]:
    """`_commune` en SQL, sans l'extension unaccent (accents des noms de communes du Nord)."""
    lowered = func.replace(func.lower(city), "œ", "oe")
    return func.translate(lowered, "-’éèêëàâîïôöûüç", " 'eeeeaaiioouuc")


def zone_sql(country: Any, city: Any, remote: Any) -> ColumnElement[str]:
    """Même règle que `zone_code`, en SQL (filtre `region` de l'API)."""
    return case(
        (country == "Madagascar", "mdg"),
        (_commune_sql(city).in_(LILLE_METRO), "lille"),
        (remote.is_(True), "remote"),
        else_="other",
    )
