from veille_pipeline.connectors.rss import RssConnector

CONNECTORS = {c.kind: c for c in (RssConnector(),)}
