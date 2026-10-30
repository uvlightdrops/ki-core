import json
import multiprocessing
import stat

import pytest
import yaml

from ki_core.config import load_config
from ki_core.runtime_settings import (
    ConflictError, EditorError, RuntimeSettings, ValidationError, resolve_runtime_candidate,
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in list(__import__("os").environ):
        if key.startswith("KI_CFG_") or key in ("KI_STAGE", "KI_PROFILE"):
            monkeypatch.delenv(key)
    (tmp_path / "ki.yaml").write_text("sample:\n  name: lower\n")
    (tmp_path / "schema").mkdir()
    schema = {
        "type": "object", "properties": {
            "sample": {"type": "object", "properties": {
                "name": {"type": "string", "default": "default"},
                "count": {"type": "integer", "minimum": 1, "default": 2},
                "flag": {"type": "boolean", "default": False},
                "choice": {"type": "string", "enum": ["a", "b"], "default": "a"},
                "optional": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "urls": {"type": "array", "items": {"type": "string"}, "default": []},
                "password": {"type": "string", "default": "schema-password"},
                "opaque": {"type": "object"},
                "domains": {"type": "object", "default": {}, "additionalProperties": {
                    "type": "object", "properties": {
                        "input_root": {"type": "string"}, "output_root": {"type": "string"},
                    }, "additionalProperties": False,
                }},
                "unsafe_map": {"type": "object", "additionalProperties": {
                    "type": "object", "properties": {"token": {"type": "string"}},
                    "additionalProperties": False,
                }},
            }},
        },
    }
    (tmp_path / "schema/sample.schema.yaml").write_text(yaml.safe_dump(schema))
    return tmp_path


def rows(service):
    return {r["path"]: r for r in service.snapshot()["rows"]}


def test_discovery_all_properties_and_dynamic_maps(project):
    service = RuntimeSettings(project)
    discovered = rows(service)
    for name in ("name", "count", "flag", "choice", "optional", "urls", "password",
                 "opaque", "domains", "unsafe_map"):
        assert f"sample.{name}" in discovered
    assert discovered["sample.domains"]["editable"]
    assert not discovered["sample.password"]["editable"]
    assert not discovered["sample.opaque"]["editable"]
    assert not discovered["sample.unsafe_map"]["editable"]
    assert "schema-password" not in json.dumps(service.snapshot())
    assert not discovered["llm.provider"]["restart_required"]


def test_containers_persist_across_reload_and_remove(project):
    service = RuntimeSettings(project)
    before = service.snapshot()
    domains = {"alpha": {"input_root": "inbox/a", "output_root": "out/a"}}
    service.save(before["revision"], {
        "sample.domains": domains, "sample.urls": ["https://example.test/"],
        "sample.optional": None, "sample.name": "runtime",
    })
    target = project / "config/runtime/runtime.yaml"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert load_config(project / "ki.yaml").get_path("sample.domains") == domains
    assert rows(RuntimeSettings(project))["sample.domains"]["effective"] == domains
    result = service.save(service.snapshot()["revision"], {}, ["sample.name"])
    assert {r["path"]: r for r in result["rows"]}["sample.name"]["effective"] == "lower"
    assert not rows(service)["sample.name"]["overridden"]
    target.chmod(0o644)
    service.save(service.snapshot()["revision"], {"sample.name": "private"})
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_field_validation_unmasked_by_environment_and_unknown_rejection(project, monkeypatch):
    service = RuntimeSettings(project)
    monkeypatch.setenv("KI_CFG_SAMPLE__COUNT", "4")
    for changes in ({"sample.count": 0}, {"sample.extra": 1},
                    {"sample.domains": {"a": {"extra": "no"}}},
                    {"sample.domains": {"token": {"input_root": "x"}}},
                    {"sample.urls": ["https://user:very-secret@example.test/"]},
                    {"sample.name": "https://example.test/?token=very-secret"}):
        with pytest.raises(EditorError) as error:
            service.save(service.snapshot()["revision"], changes)
        assert "very-secret" not in str(error.value)
    assert not service.target.exists()

@pytest.mark.parametrize("changes", [
    {"http.request_timeout": 0}, {"http.request_timeout": -1},
    {"llm.provider": "unsupported"},
])
def test_core_client_constraints_reject_unusable_overrides(project, changes):
    service = RuntimeSettings(project)
    with pytest.raises(ValidationError):
        service.save(service.snapshot()["revision"], changes)
    assert not service.target.exists()


def test_provider_enum_and_unused_provider_empty_endpoint(project):
    service = RuntimeSettings(project)
    assert set(rows(service)["llm.provider"]["enum"]) == {"auto", "ki", "openai", "ollama", "mock"}
    service.save(service.snapshot()["revision"], {
        "llm.provider": "mock", "llm.providers.ki.base_url": "",
    })


def test_higher_layers_stage_and_credentials_redaction(project, monkeypatch):
    stages = project / "config/stages"
    stages.mkdir(parents=True)
    (stages / "prod.yaml").write_text("sample:\n  name: staged\n")
    (stages / ".active_stage").write_text("prod")
    service = RuntimeSettings(project)
    assert rows(service)["sample.name"]["effective"] == "staged"
    monkeypatch.setenv("KI_CFG_SAMPLE__NAME", "environment")
    service.save(service.snapshot()["revision"], {"sample.name": "runtime"})
    assert rows(service)["sample.name"]["effective"] == "environment"
    assert rows(service)["sample.name"]["shadowed_by"] == "KI_CFG_*"
    monkeypatch.delenv("KI_CFG_SAMPLE__NAME")
    (project / "creds.yaml").write_text(
        "sample:\n  name: creds-value\n  password: private-password\n"
        "  urls:\n    - https://user:private-password@example.test/?token=private-token\n"
        "  opaque:\n    nested:\n      token: private-token\n"
        "llm:\n  providers:\n    ki:\n      base_url: https://user:private-password@example.test/\n"
    )
    snapshot = service.snapshot()
    dumped = json.dumps(snapshot)
    for secret in ("creds-value", "private-password", "private-token", "schema-password"):
        assert secret not in dumped
    assert rows(service)["sample.name"]["shadowed_by"] == "creds.yaml"
    assert not rows(service)["sample.name"]["editable"]
    service.save(service.snapshot()["revision"], {"sample.count": 3})


def test_conflicts_exclusions_and_symlinks(project):
    service = RuntimeSettings(project, excluded_paths=("sample.count",), restart_paths=("sample.flag",))
    assert not rows(service)["sample.count"]["editable"]
    assert rows(service)["sample.flag"]["restart_required"]
    revision = service.snapshot()["revision"]
    service.save(revision, {"sample.name": "first"})
    with pytest.raises(ConflictError):
        service.save(revision, {"sample.name": "second"})
    service.target.unlink()
    service.target.symlink_to(project / "ki.yaml")
    with pytest.raises(EditorError):
        service.snapshot()


def test_unknown_inventory_never_returns_values(project):
    (project / "ki.yaml").write_text("unregistered:\n  nested_token: dont-show-this\n")
    snapshot = RuntimeSettings(project).snapshot()
    unknown = {r["path"]: r for r in snapshot["rows"]}["unregistered"]
    assert not unknown["editable"]
    assert "dont-show-this" not in json.dumps(snapshot)
    assert snapshot["warnings"]


def test_nested_schema_password_and_embedded_urls_are_never_rendered(project):
    schema_file = project / "schema/sample.schema.yaml"
    schema = yaml.safe_load(schema_file.read_text())
    schema["properties"]["sample"]["properties"]["vault"] = {
        "type": "array", "items": {
            "type": "object", "properties": {
                "value": {"type": "string", "format": "password"},
            }, "additionalProperties": False,
        }, "default": [{"value": "nested-schema-secret"}],
    }
    schema_file.write_text(yaml.safe_dump(schema))
    (project / "ki.yaml").write_text(
        "sample:\n  name: 'Link: https://user:embedded-secret@example.test/path'\n"
        "  opaque:\n    arbitrary: untyped-secret\n"
    )
    service = RuntimeSettings(project)
    snapshot = service.snapshot()
    for secret in ("nested-schema-secret", "embedded-secret", "untyped-secret"):
        assert secret not in json.dumps(snapshot)
    assert not rows(service)["sample.vault"]["editable"]


def test_candidate_replaces_runtime_and_explicit_config_path(project):
    runtime = project / "config/runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.yaml").write_text("sample:\n  name: stale\n")
    explicit = project / "custom.yaml"
    explicit.write_text("sample:\n  name: custom\n")
    assert resolve_runtime_candidate(project, {}, config_path=explicit)["sample"]["name"] == "custom"
    # Resolver retains load_config's base-only validation; save validates app schema.
    assert resolve_runtime_candidate(project, {"sample": {"count": 0}})["sample"]["count"] == 0


def _process_save(root, revision, value, queue):
    try:
        RuntimeSettings(root).save(revision, {"sample.name": value})
        queue.put("saved")
    except ConflictError:
        queue.put("conflict")


def test_processes_share_lock_and_revision(project):
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    revision = RuntimeSettings(project).snapshot()["revision"]
    processes = [context.Process(target=_process_save, args=(project, revision, value, queue))
                 for value in ("one", "two")]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=2) for _ in processes) == ["conflict", "saved"]
