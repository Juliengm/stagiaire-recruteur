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
from veille_pipeline.sources_config import (
    load_defaults,
    load_sources,
    source_from_row,
    sync_yaml_to_rows,
)


@dg.asset(group_name="ingestion")
def sources_registry(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    """Reprend sources.yaml dans la table `sources` et met à jour les partitions dynamiques.

    La base est la source de vérité : le YAML crée les sources absentes et met à jour les
    autres, sauf les champs modifiés depuis l'interface ; les sources ajoutées depuis
    l'interface ne sont pas touchées. Seules les sources activées dont le connecteur existe
    sont ingérées ; `kind: unknown` et les connecteurs pas encore écrits sont ignorés.
    """
    yaml_sources = load_sources(SOURCES_FILE, resolve=False)
    defaults = load_defaults(SOURCES_FILE)
    active = []
    with Session(get_engine()) as session:
        rows = {s.id: s for s in session.scalars(select(Source))}
        new_rows, removed = sync_yaml_to_rows(yaml_sources, rows)
        session.add_all(new_rows)
        session.flush()
        for row in session.scalars(select(Source).where(Source.enabled.is_(True))):
            connector = CONNECTORS.get(row.kind)
            ready = getattr(connector, "is_configured", lambda _: True)
            if connector and ready(source_from_row(row, defaults)):
                active.append(row.id)
        total = session.scalar(select(func.count()).select_from(Source))
        session.commit()
    if removed:
        context.log.warning(f"retirées de sources.yaml, désactivées : {', '.join(removed)}")
    existing = set(context.instance.get_dynamic_partitions(sources_partitions.name))
    to_add = [s for s in active if s not in existing]
    if to_add:
        context.instance.add_dynamic_partitions(sources_partitions.name, to_add)
    for stale in existing - set(active):
        context.instance.delete_dynamic_partition(sources_partitions.name, stale)
    return dg.MaterializeResult(metadata={"sources": total or 0, "ingérables": len(active),
                                          "nouvelles": len(new_rows)})


@dg.asset(
    partitions_def=sources_partitions, deps=[sources_registry], group_name="ingestion",
    description="Appelle le connecteur de la source (une partition = une source) et upsert en base.",
)
def raw_offers(context: dg.AssetExecutionContext) -> dg.MaterializeResult:
    source_id = context.partition_key
    with Session(get_engine()) as session:
        src = source_from_row(session.get_one(Source, source_id), load_defaults(SOURCES_FILE))
    http = PoliteHttpClient(src["user_agent"], src.get("min_delay_seconds", 2))
    connector = CONNECTORS[src["kind"]]
    now = datetime.now(UTC)
    with Session(get_engine()) as session:  # permet aux connecteurs d'éviter de retélécharger
        src["known_external_ids"] = list(session.scalars(
            select(RawOffer.external_id).where(RawOffer.source_id == source_id)))
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
