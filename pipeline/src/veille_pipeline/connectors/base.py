from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol

from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

SourceConfig = dict[str, Any]


class Connector(Protocol):
    kind: str

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]: ...
