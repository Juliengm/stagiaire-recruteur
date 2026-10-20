"""Modèles pydantic : ce que les connecteurs produisent et ce que la base stocke."""
import hashlib
import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, computed_field


class RawOffer(BaseModel):
    source_id: str
    external_id: str
    url: str | None
    fetched_at: datetime
    payload: dict[str, Any]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        blob = json.dumps(self.payload, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()


class Offer(BaseModel):
    canonical_url: str | None
    title: str
    organization: str | None = None
    location_text: str | None = None
    country: str | None = None
    city: str | None = None
    remote: bool = False
    contract_type: str = "unknown"
    language: str | None = None
    posted_at: date | None = None
    deadline: date | None = None
    description: str | None = None
