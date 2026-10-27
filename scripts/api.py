"""Client minimal de l'API, pour les commandes Claude Code (`/offre`, `/candidatures`).

    cd api && uv run python ../scripts/api.py [--prod] GET /offers?q=suivi
    cd api && uv run python ../scripts/api.py [--prod] POST /offers/manual < offre.json
    cd api && uv run python ../scripts/api.py [--prod] --attendre GET /offers/manual/<id>

Dev : http://127.0.0.1:8000. Prod (`--prod`) : https://$DOMAIN/api avec la basic auth, lues dans
`.env.prod` (hors dépôt). `--attendre` répète la requête toutes les 5 s (3 min au plus) tant
qu'elle répond 404, le temps qu'un job Dagster passe. Affiche la réponse JSON ; code de sortie 1 si l'API refuse.
"""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if "=" in line and not line.lstrip().startswith("#"))


def client(prod: bool) -> httpx.Client:
    if not prod:
        return httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
    env = _env(ROOT / ".env.prod")
    return httpx.Client(base_url=f"https://{env['DOMAIN']}/api", timeout=30,
                        auth=(env["BASIC_AUTH_USER"], env["BASIC_AUTH_PASSWORD"]))


def main(args: list[str]) -> int:
    prod, wait = "--prod" in args, "--attendre" in args
    method, path = [a for a in args if a not in {"--prod", "--attendre"}]
    body = json.load(sys.stdin) if method.upper() in {"POST", "PATCH"} else None
    with client(prod) as http:
        resp = http.request(method.upper(), path, json=body)
        deadline = time.monotonic() + 180
        while wait and resp.status_code == 404 and time.monotonic() < deadline:
            time.sleep(5)
            resp = http.request(method.upper(), path, json=body)
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(resp.text)
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
