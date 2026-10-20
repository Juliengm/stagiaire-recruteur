from collections.abc import Callable

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.rss import normalize_rss

NORMALIZERS: dict[str, Callable[[dict, dict], Offer]] = {"rss": normalize_rss}
