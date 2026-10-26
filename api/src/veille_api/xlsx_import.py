"""Lecture du fichier Excel de prospection (onglets Madagascar et Lille) pour la table `applications`."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any

from db.rules import STATUSES
from openpyxl import load_workbook

SHEETS = ("Madagascar", "Lille")
FOLLOW_UP_DAYS = 10  # formule du fichier : relance = date d'envoi + 10 j si « Envoyé »

# en-tête du fichier -> colonne de la table ; Type, Ville, Fiabilité et Pourquoi ne sont pas repris
COLUMNS = {
    "Organisation": "organization", "Contact / lien": "contact", "Poste visé": "position",
    "CV à envoyer": "cv_sent", "Statut": "status", "Date d'envoi": "sent_at",
    "Relance prévue": "follow_up_at", "Notes": "notes",
}
STATUS_FR = {
    "à contacter": "interesting", "envoyé": "applied", "relancé": "applied",
    "entretien": "interview", "refusé": "rejected", "sans réponse": "ghosted",
    "abandonné": "ignored",
}


@dataclass
class ParsedSheet:
    rows: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)  # {sheet, row, reason}


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    raise ValueError(f"date illisible : {value!r}")


def _number(value: Any) -> int:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValueError(f"N° absent ou non numérique : {value!r}") from None


def _status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "new"
    if text in STATUSES:
        return text
    if text in STATUS_FR:
        return STATUS_FR[text]
    raise ValueError(f"statut inconnu : {value!r}")


def parse_workbook(content: bytes) -> ParsedSheet:
    """Lignes à importer (clé : onglet + N°) et lignes ignorées avec leur motif."""
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)  # valeurs des formules
    out = ParsedSheet()
    for sheet in SHEETS:
        if sheet not in wb.sheetnames:
            out.skipped.append({"sheet": sheet, "row": None, "reason": "onglet absent"})
            continue
        rows = wb[sheet].iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows, ())]
        if "N°" not in header or "Organisation" not in header:
            out.skipped.append({"sheet": sheet, "row": None, "reason": "en-têtes N° / Organisation absents"})
            continue
        idx = {name: header.index(name) for name in ("N°", *COLUMNS) if name in header}
        for line, values in enumerate(rows, start=2):
            cell = {name: values[i] if i < len(values) else None for name, i in idx.items()}
            if not any(v not in (None, "") for v in cell.values()):
                continue  # ligne vide (l'onglet peut s'étendre jusqu'à la ligne 1 048 576)
            try:
                if not str(cell.get("Organisation") or "").strip():
                    raise ValueError("organisation vide")
                row: dict[str, Any] = {"sheet": sheet, "sheet_row": _number(cell.get("N°"))}
                for name, column in COLUMNS.items():
                    value = cell.get(name)
                    row[column] = str(value).strip() if value not in (None, "") else None
                row["status"] = _status(cell.get("Statut"))
                row["sent_at"] = _date(cell.get("Date d'envoi"))
                follow_up = cell.get("Relance prévue")
                if isinstance(follow_up, str) and follow_up.startswith("="):
                    follow_up = None  # formule sans valeur calculée (fichier jamais ouvert)
                row["follow_up_at"] = _date(follow_up)
                if row["follow_up_at"] is None and row["status"] == "applied" and row["sent_at"]:
                    row["follow_up_at"] = row["sent_at"] + timedelta(days=FOLLOW_UP_DAYS)
            except ValueError as exc:
                out.skipped.append({"sheet": sheet, "row": line, "reason": str(exc)})
                continue
            out.rows.append(row)
    return out
