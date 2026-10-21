from veille_pipeline.connectors.csv_dataset import CsvDatasetConnector
from veille_pipeline.connectors.reliefweb import ReliefWebConnector
from veille_pipeline.connectors.rss import RssConnector
from veille_pipeline.connectors.worldbank import WorldBankProcNoticesConnector

CONNECTORS = {c.kind: c for c in (RssConnector(), CsvDatasetConnector(), ReliefWebConnector(),
                                         WorldBankProcNoticesConnector())}
