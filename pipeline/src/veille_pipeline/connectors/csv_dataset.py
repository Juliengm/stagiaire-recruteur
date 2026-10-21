"""Connecteur pour les jeux de données CSV publics (Choisir le service public, ~120 Mo).

Le fichier est lu en flux : jamais chargé en mémoire. Seules les offres du département demandé
et encore publiées sont conservées ; une référence apparaît parfois sur plusieurs lignes.
"""
import csv
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

OFFER_URL = "https://choisirleservicepublic.gouv.fr/offre-emploi/{ref}/"
COL_REF, COL_LOCALISATION, COL_FIN = "Référence", "Localisation du poste", "Date de fin de publication par défaut"


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


class CsvDatasetConnector:
    kind = "csv_dataset"

    def parse(
        self, lines: Iterable[str], source: SourceConfig, today: date | None = None
    ) -> list[RawOffer]:
        today = today or date.today()
        departement = str(source["config"].get("filter", {}).get("departement", ""))
        now = datetime.now(UTC)
        seen: set[str] = set()
        offers = []
        for row in csv.DictReader(lines, delimiter=";"):
            ref = row[COL_REF]
            if ref in seen:
                continue
            if departement and f"({departement})" not in row[COL_LOCALISATION]:
                continue
            end = _parse_date(row[COL_FIN])
            if end is None or end < today:
                continue
            seen.add(ref)
            offers.append(
                RawOffer(
                    source_id=source["id"], external_id=ref, url=OFFER_URL.format(ref=ref),
                    fetched_at=now, payload={k: v for k, v in row.items() if v},
                )
            )
        return offers

    def _stream_lines(self, source: SourceConfig, http: PoliteHttpClient) -> Iterator[str]:
        url = source["config"]["url"]
        if not http.allowed(url):
            raise PermissionError(f"robots.txt interdit {url}")
        with http._client.stream("GET", url) as resp:  # flux : pas de http.get, fichier trop gros
            resp.raise_for_status()
            yield from resp.iter_lines()

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        return self.parse(self._stream_lines(source, http), source)
