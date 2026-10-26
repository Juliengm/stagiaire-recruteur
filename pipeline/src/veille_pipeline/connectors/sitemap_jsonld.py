"""Connecteur « sitemap + JSON-LD » : liste les offres d'un sitemap, lit le JobPosting schema.org de chaque page."""
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from selectolax.lexbor import LexborHTMLParser

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

MAX_PAGES = 60
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def sitemap_urls(xml: str | bytes, url_filter: str | None) -> list[str]:
    root = ET.fromstring(xml)
    urls = [(e.text or "").strip() for e in root.iter(f"{_NS}loc")]
    pattern = re.compile(url_filter) if url_filter else None
    return [u for u in urls if u and (pattern is None or pattern.search(u))]


def job_posting(html: str) -> dict[str, Any] | None:
    for node in LexborHTMLParser(html).css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


class SitemapJsonLdConnector:
    kind = "sitemap_jsonld"

    def is_configured(self, source: SourceConfig) -> bool:
        return bool(source.get("config", {}).get("sitemap"))

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        known = set(source.get("known_external_ids", ()))
        urls = sitemap_urls(http.get(config["sitemap"]).content, config.get("url_filter"))
        offers = []
        # seules les pages inconnues sont téléchargées, dans la limite de `max_pages` par exécution
        for url in [u for u in urls if u not in known][: int(config.get("max_pages", MAX_PAGES))]:
            posting = job_posting(http.get(url).text)
            if posting:
                offers.append(RawOffer(
                    source_id=source["id"], external_id=url, url=url,
                    fetched_at=datetime.now(UTC), payload=posting))
        return offers
