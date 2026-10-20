"""Connecteur RSS générique (feedparser), avec filtre local et mapping de champs."""
import calendar
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer


def passes_local_filter(entry: dict[str, Any], local_filter: dict[str, Any] | None) -> bool:
    if not local_filter:
        return True
    text = " ".join(str(entry.get(k, "")) for k in ("title", "summary", "link")).lower()
    if (needles := local_filter.get("any_text")) and not any(n.lower() in text for n in needles):
        return False
    return not (
        (fragment := local_filter.get("url_contains")) and fragment not in entry.get("link", "")
    )


def _entry_payload(entry: Any) -> dict[str, Any]:
    published = None
    if entry.get("published_parsed"):
        published = datetime.fromtimestamp(
            calendar.timegm(entry.published_parsed), tz=UTC
        ).isoformat()
    return {
        "title": entry.get("title"),
        "link": entry.get("link"),
        "summary": entry.get("summary"),
        "content": (entry.get("content") or [{}])[0].get("value"),
        "published": published,
        "category": entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None,
        "author": entry.get("author"),
    }


class RssConnector:
    kind = "rss"

    def parse(self, xml: str | bytes, source: SourceConfig, source_id: str) -> list[RawOffer]:
        config = source["config"]
        feed = feedparser.parse(xml)
        now = datetime.now(UTC)
        offers = []
        for entry in feed.entries:
            payload = _entry_payload(entry)
            if not payload["link"] or not passes_local_filter(payload, config.get("local_filter")):
                continue
            offers.append(
                RawOffer(
                    source_id=source_id,
                    external_id=entry.get("id") or payload["link"],
                    url=payload["link"],
                    fetched_at=now,
                    payload=payload,
                )
            )
        return offers

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        urls = [config["url"]] + ([config["fallback_url"]] if config.get("fallback_url") else [])
        last_error: Exception | None = None
        for url in urls:
            try:
                return self.parse(http.get(url).content, source, source["id"])
            except (httpx.HTTPError, PermissionError) as exc:  # repli sur fallback_url puis on remonte l'erreur
                last_error = exc
        raise RuntimeError(f"source {source['id']} injoignable : {last_error}")
