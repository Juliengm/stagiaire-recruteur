"""Connecteur de pages HTML listant des offres : sélecteurs CSS configurables, pagination."""
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.lexbor import LexborHTMLParser, LexborNode

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

FIELDS = ("title", "url", "organization", "location", "country", "city", "contract", "posted",
          "deadline", "id")


def _extract(node: LexborNode, spec: str | dict[str, str] | None) -> str | None:
    """`spec` : « css », « css@attribut » ou {css, attr, regex} ; sans css, le nœud lui-même."""
    if spec is None:
        return None
    if isinstance(spec, str):
        css, _, attr = spec.partition("@")
        spec = {"css": css, "attr": attr}
    target = node.css_first(spec["css"]) if spec.get("css") else node
    if target is None:
        return None
    value = target.attributes.get(spec["attr"]) if spec.get("attr") else target.text(separator=" ")
    value = re.sub(r"\s+", " ", value or "").strip()
    if value and spec.get("regex"):
        match = re.search(spec["regex"], value)
        value = (match.group(1) if match else "").strip()
    return value or None


class HtmlListConnector:
    kind = "html_list"

    def is_configured(self, source: SourceConfig) -> bool:
        return bool(source.get("config", {}).get("selectors"))

    def parse(self, html: str, page_url: str, source: SourceConfig) -> list[RawOffer]:
        config = source["config"]
        selectors = config["selectors"]
        now = datetime.now(UTC)
        offers = []
        for node in LexborHTMLParser(html).css(selectors["item"]):
            payload: dict[str, Any] = {f: _extract(node, selectors.get(f)) for f in FIELDS}
            if not payload["title"] or not payload["url"]:
                continue
            payload["url"] = urljoin(page_url, payload["url"])
            offers.append(RawOffer(
                source_id=source["id"], external_id=payload.pop("id") or payload["url"],
                url=payload["url"], fetched_at=now, payload=payload))
        return offers

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        urls = [config["url"], *config.get("extra_urls", [])]
        for url in urls:  # robots.txt vérifié avant tout appel, pour toutes les pages
            if not http.allowed(url):
                raise PermissionError(f"robots.txt interdit {url}")
        found: dict[str, RawOffer] = {}
        for base in urls:
            for page in range(1, int(config.get("max_pages", 1)) + 1):
                page_url = base if page == 1 else config["pagination"].format(url=base, n=page)
                try:
                    html = http.get(page_url).text
                except httpx.HTTPStatusError as exc:
                    if page > 1 and exc.response.status_code == 404:
                        break  # fin de la pagination
                    raise
                new = [o for o in self.parse(html, page_url, source)
                       if o.external_id not in found]
                if not new:
                    break
                found.update({o.external_id: o for o in new})
                if "pagination" not in config:
                    break
        return list(found.values())
