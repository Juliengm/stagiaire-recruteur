from datetime import UTC, datetime

import dagster as dg
from db.models import RawOffer, Source
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_pipeline.connectors import CONNECTORS
from veille_pipeline.db import get_engine
from veille_pipeline.defs.assets.common import SOURCES_FILE, sources_partitions
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.sources_config import load_sources


@dg.asset(group_name="ingestion")
def sources_registry(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Synchronise sources.yaml vers la table `sources` et les partitions dynamiques.

    Seules les sources activées dont le connecteur existe sont ingérées ; `kind: unknown`
    et les connecteurs pas encore écrits sont ignorés.
    """
    sources = load_sources(SOURCES_FILE)
    active = []
    with Session(get_engine()) as session:
        for src in sources:
            stmt = insert(Source).values(
                id=src["id"], name=src.get("name"), kind=src["kind"], config=src.get("config", {}),
                region=src.get("region", []), priority=src.get("priority"),
                schedule=src.get("schedule", "daily"), enabled=src.get("enabled", True),
            )
            session.execute(stmt.on_conflict_do_update(
                index_elements=[Source.id],
                set_={"name": stmt.excluded.name, "kind": stmt.excluded.kind,
                      "config": stmt.excluded.config, "region": stmt.excluded.region,
                      "priority": stmt.excluded.priority, "schedule": stmt.excluded.schedule,
                      "enabled": stmt.excluded.enabled},
            ))
            if src.get("enabled", True) and src["kind"] in CONNECTORS:
                active.append(src["id"])
        session.commit()
    existing = set(context.instance.get_dynamic_partitions(sources_partitions.name))
    to_add = [s for s in active if s not in existing]
    if to_add:
        context.instance.add_dynamic_partitions(sources_partitions.name, to_add)
    for stale in existing - set(active):
        context.instance.delete_dynamic_partition(sources_partitions.name, stale)
    return dg.MaterializeResult(metadata={"sources": len(sources), "ingérables": len(active)})


@dg.asset(
    partitions_def=sources_partitions, deps=[sources_registry], group_name="ingestion",
    description="Appelle le connecteur de la source (une partition = une source) et upsert en base.",
)
def raw_offers(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    source_id = context.partition_key
    src = next(s for s in load_sources(SOURCES_FILE) if s["id"] == source_id)
    http = PoliteHttpClient(src["user_agent"], src.get("min_delay_seconds", 2))
    connector = CONNECTORS[src["kind"]]
    now = datetime.now(UTC)
    try:
        offers = list(connector.fetch(src, None, http))
    except Exception as exc:
        with Session(get_engine()) as session:
            session.execute(update(Source).where(Source.id == source_id).values(
                last_error=str(exc)[:500],
                consecutive_failures=Source.consecutive_failures + 1))
            session.commit()
        raise
    with Session(get_engine()) as session:
        known = set(session.scalars(
            select(RawOffer.external_id).where(RawOffer.source_id == source_id)))
        new_count = sum(1 for o in offers if o.external_id not in known)
        for offer in offers:
            stmt = insert(RawOffer).values(
                source_id=offer.source_id, external_id=offer.external_id, url=offer.url,
                payload=offer.payload, content_hash=offer.content_hash, fetched_at=offer.fetched_at)
            session.execute(stmt.on_conflict_do_update(
                index_elements=[RawOffer.source_id, RawOffer.external_id],
                set_={"payload": stmt.excluded.payload, "content_hash": stmt.excluded.content_hash,
                      "url": stmt.excluded.url, "fetched_at": stmt.excluded.fetched_at}))
        session.execute(update(Source).where(Source.id == source_id).values(
            last_success_at=now, last_error=None, consecutive_failures=0,
            consecutive_empty_runs=0 if new_count else Source.consecutive_empty_runs + 1))
        session.commit()
        total = session.scalar(
            select(func.count()).select_from(RawOffer).where(RawOffer.source_id == source_id))
    finalize = getattr(connector, "finalize", None)
    if finalize:  # ex. e-mails : marqués « traités » seulement une fois les offres en base
        context.log.info(f"{finalize(src)} message(s) marqué(s) comme traités")
    return dg.MaterializeResult(metadata={"récupérées": len(offers), "nouvelles": new_count, "total_en_base": total})
