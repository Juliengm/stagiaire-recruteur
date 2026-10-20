import os
from pathlib import Path

import dagster as dg

SOURCES_FILE = Path(os.environ.get("SOURCES_FILE", "/app/sources.yaml"))
SCORING_FILE = Path(os.environ.get("SCORING_FILE", "/app/config/scoring.yaml"))
sources_partitions = dg.DynamicPartitionsDefinition(name="sources")
