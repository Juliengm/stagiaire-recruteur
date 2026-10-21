from collections.abc import Callable

from veille_pipeline.models import Offer
from veille_pipeline.normalizers.csv_dataset import normalize_csv_dataset
from veille_pipeline.normalizers.reliefweb import normalize_reliefweb
from veille_pipeline.normalizers.rss import normalize_rss
from veille_pipeline.normalizers.worldbank import normalize_worldbank

NORMALIZERS: dict[str, Callable[[dict, dict], Offer]] = {
    "rss": normalize_rss,
    "csv_dataset": normalize_csv_dataset,
    "reliefweb_api": normalize_reliefweb,
    "worldbank_procnotices": normalize_worldbank,
}
