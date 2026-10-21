"""Date limite repérée dans un texte libre (anglais ou français)."""
import re
from datetime import date

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}
_DEADLINE = re.compile(
    r"(?:deadline|closing date|close[sd]? on|date limite|date de clôture|avant le)"
    r"[^0-9]{0,40}(\d{1,2})(?:st|nd|rd|th|er)?\s+([A-Za-zéûè]+)\s+(\d{4})", re.IGNORECASE)


def find_deadline(text: str) -> date | None:
    for day, month, year in _DEADLINE.findall(text):
        if (m := _MONTHS.get(month.lower())) is not None:
            try:
                return date(int(year), m, int(day))
            except ValueError:
                continue
    return None
