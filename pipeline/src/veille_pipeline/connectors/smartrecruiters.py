"""Connecteur SmartRecruiters : API publique des offres `api.smartrecruiters.com/v1/companies/{id}/postings`.

robots.txt de api.smartrecruiters.com interdit tout aux robots (sauf LinkedInBot) : le client
HTTP le respecte, la source Kiabi est donc désactivée et passe par les alertes e-mail. Le
connecteur reste prêt si l'éditeur ouvre son API aux robots.
"""
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
PAGE_SIZE = 100


def _norm(value: str | None) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return folded.lower().strip()


class SmartRecruitersConnector:
    kind = "smartrecruiters"

    def matches(self, posting: dict[str, Any], config: dict[str, Any]) -> bool:
        location = posting.get("location") or {}
        countries = {_norm(c) for c in config.get("countries", [])}
        cities = {_norm(c) for c in config.get("cities", [])}
        if countries and _norm(location.get("country")) not in countries:
            return False
        return not cities or _norm(location.get("city")) in cities

    def parse(self, data: dict[str, Any], source: SourceConfig) -> list[RawOffer]:
        now = datetime.now(UTC)
        return [
            RawOffer(source_id=source["id"], external_id=str(p["id"]), url=None, fetched_at=now,
                     payload=p)
            for p in data.get("content", []) if self.matches(p, source["config"])
        ]

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        base = API.format(company=config["company_id"])
        postings: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = http.get(f"{base}?limit={PAGE_SIZE}&offset={offset}").json()
            postings += page.get("content", [])
            offset += PAGE_SIZE
            if offset >= page.get("totalFound", 0) or not page.get("content"):
                break
        offers = self.parse({"content": postings}, source)
        known = set(source.get("known_external_ids", ()))
        for offer in offers:  # le détail (description, URL publique) n'est lu que pour les nouvelles offres
            if offer.external_id in known:
                continue
            detail = http.get(f"{base}/{offer.external_id}").json()
            offer.payload = {**offer.payload, "detail": detail}
            offer.url = detail.get("postingUrl")
        return offers
