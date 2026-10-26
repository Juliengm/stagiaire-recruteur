from db.models import Source
from db.rules import CONNECTOR_KINDS

from veille_pipeline.connectors import CONNECTORS
from veille_pipeline.sources_config import source_from_row, sync_yaml_to_rows


def _yaml(**kw: object) -> dict:
    return {"id": "s1", "name": "Source 1", "kind": "rss", "config": {"url": "https://a"},
            "region": ["mdg"], "priority": 1, **kw}


def _row(**kw: object) -> Source:
    base: dict = {"id": "s1", "name": "Source 1", "kind": "rss", "config": {"url": "https://a"},
                  "region": ["mdg"], "priority": 1, "schedule": "daily", "enabled": True,
                  "origin": "yaml", "user_fields": []}
    return Source(**{**base, **kw})


def test_connector_kinds_match_connectors() -> None:
    assert set(CONNECTORS) == CONNECTOR_KINDS


def test_new_yaml_source_is_inserted() -> None:
    new, removed = sync_yaml_to_rows([_yaml()], {})
    assert [r.id for r in new] == ["s1"] and new[0].origin == "yaml" and removed == []


def test_yaml_updates_fields_not_edited_in_interface() -> None:
    row = _row(enabled=False, priority=3, user_fields=["enabled"])
    new, _ = sync_yaml_to_rows([_yaml(config={"url": "https://b"}, enabled=True)], {"s1": row})
    assert new == []
    assert row.config == {"url": "https://b"} and row.priority == 1  # repris du YAML
    assert row.enabled is False                                    # choix fait dans l'interface


def test_interface_sources_untouched_and_removed_yaml_sources_disabled() -> None:
    api = _row(id="api1", origin="api")
    gone = _row(id="gone")
    _, removed = sync_yaml_to_rows([_yaml()], {"s1": _row(), "api1": api, "gone": gone})
    assert removed == ["gone"] and gone.enabled is False and api.enabled is True


def test_source_from_row_resolves_vars_only_for_the_connector(monkeypatch) -> None:
    monkeypatch.setenv("APPNAME", "secret")
    row = _row(config={"appname": "${APPNAME}"})
    src = source_from_row(row, {"user_agent": "UA", "min_delay_seconds": 2})
    assert src["config"] == {"appname": "secret"} and src["user_agent"] == "UA"
    assert row.config == {"appname": "${APPNAME}"}  # la base garde le gabarit
