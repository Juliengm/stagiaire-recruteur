"""Connecteur Workable : widget public `apply.workable.com/api/v1/widget/accounts/{compte}`."""
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

WIDGET = "https://apply.workable.com/api/v1/widget/accounts/{account}?details=true"


class WorkableConnector:
    kind = "workable"

    def parse(self, data: dict[str, Any], source: SourceConfig) -> list[RawOffer]:
        config = source["config"]
        countries = {c.lower() for c in config.get("countries", [])}
        now = datetime.now(UTC)
        offers = []
        for job in data.get("jobs", []):
            if countries and (job.get("country") or "").lower() not in countries:
                continue
            offers.append(RawOffer(
                source_id=source["id"], external_id=job["shortcode"], url=job["url"],
                fetched_at=now, payload={**job, "company": data.get("name")}))
        return offers

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        url = WIDGET.format(account=source["config"]["account"])
        return self.parse(http.get(url).json(), source)
