"""Connecteur des avis de passation de marchés de la Banque mondiale (API publique, sans clé).

Seules les demandes de manifestation d'intérêt encore ouvertes sont gardées ; par défaut les
consultants individuels (`INDV`), les autres méthodes visant des cabinets.
"""
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

NOTICE_URL = "https://projects.worldbank.org/en/projects-operations/procurement-detail/{id}"
FIELDS = (
    "id,notice_type,noticedate,submission_date,submission_deadline_date,project_ctry_name,"
    "project_id,project_name,bid_reference_no,bid_description,procurement_group,"
    "procurement_method_code,procurement_method_name,contact_organization,contact_email,"
    "notice_lang_name,notice_text"
)


def _deadline(notice: dict[str, Any]) -> date | None:
    raw = (notice.get("submission_deadline_date") or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


class WorldBankProcNoticesConnector:
    kind = "worldbank_procnotices"

    def parse(
        self, data: dict[str, Any], source: SourceConfig, today: date | None = None
    ) -> list[RawOffer]:
        today = today or date.today()
        keep = source["config"].get("keep_if", {})
        methods = keep.get("method_codes", ["INDV"])
        now = datetime.now(UTC)
        offers = []
        for notice in data.get("procnotices", []):
            deadline = _deadline(notice)
            if deadline is None or deadline < today:
                continue
            if methods and notice.get("procurement_method_code") not in methods:
                continue
            offers.append(
                RawOffer(
                    source_id=source["id"], external_id=notice["id"],
                    url=NOTICE_URL.format(id=notice["id"]), fetched_at=now, payload=notice,
                )
            )
        return offers

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        params = {**config["params"], "fl": FIELDS}
        rows = int(params.get("rows", 100))
        offers: list[RawOffer] = []
        for page in range(int(config.get("max_pages", 2))):
            params["os"] = page * rows
            data = http.get(config["endpoint"], params=params, check_robots=False).json()
            offers += self.parse(data, source)
            if len(data.get("procnotices", [])) < rows:
                break
        return offers
