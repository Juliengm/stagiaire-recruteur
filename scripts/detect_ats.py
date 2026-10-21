"""Identifie l'ATS des sources `kind: unknown` de sources.yaml (robots.txt et délai respectés).

    cd pipeline && uv run python ../scripts/detect_ats.py [id_de_source ...]
"""
import os
import sys
from pathlib import Path

import httpx

from veille_pipeline.ats import HINTS, detect_ats
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.sources_config import load_sources

ROOT = Path(__file__).resolve().parents[1]


def main(wanted: list[str]) -> int:
    os.environ.setdefault("CONTACT_EMAIL", "contact@example.org")
    sources = load_sources(ROOT / "sources.yaml")
    todo = [s for s in sources if (s["id"] in wanted if wanted else s["kind"] == "unknown")]
    for src in todo:
        http = PoliteHttpClient(src["user_agent"], src.get("min_delay_seconds", 2))
        url = src["config"]["url"]
        try:
            resp = http.get(url)
        except (httpx.HTTPError, PermissionError) as exc:
            print(f"{src['id']}: {url} → injoignable ou interdit ({exc})")
            continue
        found = detect_ats(str(resp.url), resp.text, dict(resp.headers))
        print(f"{src['id']}: {url} → {', '.join(found) or 'aucun ATS reconnu'}")
        for name in found:
            if name in HINTS:
                print(f"    {HINTS[name]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
