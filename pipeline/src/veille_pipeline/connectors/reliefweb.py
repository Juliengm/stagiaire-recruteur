"""Connecteur ReliefWeb API v2 (lecture seule). L'`appname` doit être validé par ReliefWeb."""
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer


class ReliefWebConnector:
    kind = "reliefweb_api"

    def parse(self, data: dict[str, Any], source_id: str) -> list[RawOffer]:
        now = datetime.now(UTC)
        offers = []
        for item in data.get("data", []):
            fields = item["fields"]
            offers.append(
                RawOffer(
                    source_id=source_id, external_id=str(item["id"]), url=fields.get("url"),
                    fetched_at=now, payload=fields,
                )
            )
        return offers

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        if not config.get("appname"):
            raise RuntimeError("RELIEFWEB_APPNAME manquant (appname validé par ReliefWeb requis)")
        resp = http.post(
            config["endpoint"], params={"appname": config["appname"]}, json=config["body"],
            check_robots=False,  # API officielle, appname validé par ReliefWeb
        )
        return self.parse(resp.json(), source["id"])
