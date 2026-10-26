import dagster as dg
from db.models import Source
from sqlalchemy import select
from sqlalchemy.orm import Session

from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.digest import rapport_du_stagiaire
from veille_pipeline.defs.assets.ingest import raw_offers, sources_registry
from veille_pipeline.defs.assets.process import (
    cv_embeddings,
    offers_deduped,
    offers_normalized,
    offers_scored,
)

TZ = "Indian/Antananarivo"

ingest_job = dg.define_asset_job("ingest_job", selection=[raw_offers])
process_job = dg.define_asset_job(
    "process_job", selection=[offers_normalized, offers_deduped, cv_embeddings, offers_scored])
digest_job = dg.define_asset_job("digest_job", selection=[rapport_du_stagiaire])
registry_job = dg.define_asset_job("registry_job", selection=[sources_registry])


def _due_partitions(frequency: str) -> list[str]:
    with Session(get_engine()) as session:
        return list(session.scalars(
            select(Source.id).where(Source.enabled, Source.schedule == frequency)))


@dg.schedule(cron_schedule="0 5 * * *", execution_timezone=TZ, job=ingest_job)
def daily_ingest(context: dg.ScheduleEvaluationContext):
    known = set(context.instance.get_dynamic_partitions("sources"))
    for source_id in _due_partitions("daily"):
        if source_id in known:
            yield dg.RunRequest(partition_key=source_id, run_key=f"{source_id}-{context.scheduled_execution_time:%Y%m%d}")


@dg.schedule(cron_schedule="30 4 * * 1", execution_timezone=TZ, job=ingest_job)
def weekly_ingest(context: dg.ScheduleEvaluationContext):
    known = set(context.instance.get_dynamic_partitions("sources"))
    for source_id in _due_partitions("weekly"):
        if source_id in known:
            yield dg.RunRequest(partition_key=source_id, run_key=f"{source_id}-{context.scheduled_execution_time:%Y%m%d}")


# L'aval n'est pas partitionné : il traite tout ce qui est arrivé après l'ingestion de 05:00.
process_schedule = dg.ScheduleDefinition(
    name="daily_process", job=process_job, cron_schedule="30 5 * * *", execution_timezone=TZ)
digest_schedule = dg.ScheduleDefinition(
    name="digest_schedule", job=digest_job, cron_schedule="0 7 * * 1,4", execution_timezone=TZ)
registry_schedule = dg.ScheduleDefinition(
    name="registry_schedule", job=registry_job, cron_schedule="0 4 * * *", execution_timezone=TZ)
