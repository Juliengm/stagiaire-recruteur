"""« Lancer maintenant » : déclenche un job Dagster par son API GraphQL (réseau interne)."""
import os
from typing import Annotated, Any, Literal

import httpx
from db.models import Source
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["dagster"])

LOCATION, REPOSITORY = "veille_pipeline", "__repository__"
JOBS = {"registry": "registry_job", "ingest": "ingest_job", "process": "process_job",
        "digest": "digest_job"}

LAUNCH = """
mutation Launch($params: ExecutionParams!) {
  launchRun(executionParams: $params) {
    __typename
    ... on LaunchRunSuccess { run { runId } }
    ... on Error { message }
    ... on RunConfigValidationInvalid { errors { message } }
  }
}"""


class RunIn(BaseModel):
    job: Literal["registry", "ingest", "process", "digest"]
    source_id: str | None = None  # obligatoire pour « ingest » (une partition = une source)


class RunOut(BaseModel):
    run_id: str
    url: str


def graphql_url() -> str:
    return os.environ.get("DAGSTER_GRAPHQL_URL", "http://dagster-webserver:3000/dagster/graphql")


def get_http() -> httpx.Client:
    return httpx.Client(timeout=20)


@router.post("/runs", status_code=201)
def launch_run(body: RunIn, session: Annotated[Session, Depends(get_session)],
               http: Annotated[httpx.Client, Depends(get_http)]) -> RunOut:
    tags: list[dict[str, str]] = []
    if body.job == "ingest":
        if not body.source_id:
            raise HTTPException(422, "source_id obligatoire pour une ingestion")
        source = session.get(Source, body.source_id)
        if source is None:
            raise HTTPException(404, "source inconnue")
        if not source.enabled:
            raise HTTPException(409, "source désactivée")
        tags.append({"key": "dagster/partition", "value": source.id})
    params: dict[str, Any] = {
        "selector": {"repositoryLocationName": LOCATION, "repositoryName": REPOSITORY,
                     "jobName": JOBS[body.job]},
        "executionMetadata": {"tags": tags},
        "runConfigData": {},
    }
    try:
        resp = http.post(graphql_url(), json={"query": LAUNCH, "variables": {"params": params}})
        resp.raise_for_status()
        result = resp.json()["data"]["launchRun"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, f"Dagster injoignable : {exc}") from exc
    if result["__typename"] != "LaunchRunSuccess":
        errors = [e["message"] for e in result.get("errors", [])]
        detail = result.get("message") or "; ".join(errors) or result["__typename"]
        # ex. partition absente : source ajoutée mais `sources_registry` pas encore passé
        raise HTTPException(409, f"Dagster a refusé le lancement : {detail}")
    run_id = result["run"]["runId"]
    return RunOut(run_id=run_id, url=f"/dagster/runs/{run_id}")
