import json
import multiprocessing
import stat

import pytest
import yaml

from ki_core.config import load_config
from ki_core.runtime_settings import ConflictError, EditorError, RuntimeSettings, ValidationError


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in list(__import__("os").environ):
        if key.startswith("KI_CFG_") or key in ("KI_STAGE", "KI_PROFILE"):
            monkeypatch.delenv(key)
    (tmp_path / "ki.yaml").write_text("llm:\n  provider: mock\n")
    (tmp_path / "schema").mkdir()
    schema = {"type": "object", "properties": {"auth": {"type": "object", "properties": {
        "password": {"type": "string", "pattern": "^$|^.{5,}$"},
        "token": {"type": "string"}, "api_key": {"type": ["string", "null"]},
        "dsn": {"type": "string"},
        "count": {"type": "integer"},
    }}}}
    (tmp_path / "schema/auth.schema.yaml").write_text(yaml.safe_dump(schema))
    return tmp_path


def test_write_only_persistence_permissions_and_reload(project):
    service = RuntimeSettings(project)
    snap = service.secret_snapshot()
    assert not {r["path"]: r for r in snap["rows"]}["auth.password"]["configured"]
    result = service.save_secret(snap["revision"], "auth.password", "synthetic-password")
    assert result["revision"] != snap["revision"]
    assert stat.S_IMODE((project / "creds.yaml").stat().st_mode) == 0o600
    assert load_config(project / "ki.yaml").get_path("auth.password") == "synthetic-password"
    assert "synthetic-password" not in json.dumps(result)
    assert "synthetic-password" not in json.dumps(service.snapshot())
    assert {r["path"]: r for r in RuntimeSettings(project).secret_snapshot()["rows"]}["auth.password"]["configured"]
    (project / "creds.yaml").chmod(0o644)
    service.save_secret(result["revision"], "auth.token", "another-synthetic-token")
    assert stat.S_IMODE((project / "creds.yaml").stat().st_mode) == 0o600


def test_conflict_blank_and_unknown_paths(project):
    service = RuntimeSettings(project)
    before = service.secret_snapshot()
    assert service.save_secret(before["revision"], "auth.token", "") == before
    assert not (project / "creds.yaml").exists()
    result = service.save_secret(before["revision"], "auth.token", "synthetic-token")
    for value in ("new-synthetic", ""):
        with pytest.raises(ConflictError):
            service.save_secret(before["revision"], "auth.token", value)
    for path in ("auth.count", "unknown.password", "../creds.yaml", "auth"):
        with pytest.raises(ValidationError):
            service.save_secret(result["revision"], path, "never-return-this")
    with pytest.raises(ValidationError) as error:
        service.save_secret(result["revision"], "auth.password", "bad")
    assert "bad" not in str(error.value)
    assert "never-return-this" not in json.dumps(service.secret_snapshot())


def test_remove_replaces_creds_and_falls_back_to_env_runtime(project, monkeypatch):
    service = RuntimeSettings(project)
    runtime = project / "config/runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.yaml").write_text("auth:\n  token: runtime-fallback\n")
    monkeypatch.setenv("KI_CFG_AUTH__TOKEN", "env-fallback")
    result = service.save_secret(service.secret_snapshot()["revision"], "auth.token", "credentials-winner")
    assert load_config(project / "ki.yaml").get_path("auth.token") == "credentials-winner"
    result = service.remove_secret(result["revision"], "auth.token")
    row = {r["path"]: r for r in result["rows"]}["auth.token"]
    assert row["configured"] and not row["overridden"]
    assert load_config(project / "ki.yaml").get_path("auth.token") == "env-fallback"
    monkeypatch.delenv("KI_CFG_AUTH__TOKEN")
    assert load_config(project / "ki.yaml").get_path("auth.token") == "runtime-fallback"
    assert "fallback" not in json.dumps(service.secret_snapshot())


def test_symlinks_exclusions_external_creds(project, monkeypatch):
    service = RuntimeSettings(project, excluded_paths=("auth.password",), restart_paths=("auth.token",))
    assert not {r["path"]: r for r in service.secret_snapshot()["rows"]}["auth.password"]["editable"]
    assert {r["path"]: r for r in service.secret_snapshot()["rows"]}["auth.token"]["restart_required"]
    assert {r["path"]: r for r in service.secret_snapshot()["rows"]}["auth.dsn"]["restart_required"]
    with pytest.raises(ValidationError):
        service.save_secret(service.secret_snapshot()["revision"], "auth.password", "synthetic-password")
    outside = project / "outside.yaml"
    outside.write_text("auth:\n  token: synthetic-external\n")
    (project / "creds.yaml").symlink_to(outside)
    with pytest.raises(EditorError):
        service.secret_snapshot()
    with pytest.raises(EditorError):
        service.save_secret("", "auth.token", "synthetic-password")
    (project / "creds.yaml").unlink()
    external_home = project / "external-home"
    external = external_home / ".config/ki/creds.yaml"
    external.parent.mkdir(parents=True)
    external.write_text("auth:\n  token: external-synthetic-value\n")
    monkeypatch.setenv("HOME", str(external_home))
    with pytest.raises(EditorError) as error:
        service.secret_snapshot()
    assert "external-synthetic-value" not in str(error.value)
    assert not (project / "creds.yaml").exists()


def test_existing_config_creds_chosen_without_migration_and_placeholder_hidden(project):
    target = project / "config/creds.yaml"
    target.parent.mkdir()
    target.write_text("auth:\n  token: ${SYNTHETIC_TOKEN}\n")
    service = RuntimeSettings(project)
    snap = service.secret_snapshot()
    assert snap["target"] == "config/creds.yaml"
    assert "${SYNTHETIC_TOKEN}" not in json.dumps(snap)
    result = service.save_secret(snap["revision"], "auth.token", "synthetic-replacement")
    assert not (project / "creds.yaml").exists()
    assert "synthetic-replacement" not in json.dumps(result)
    assert yaml.safe_load(target.read_text())["auth"]["token"] == "synthetic-replacement"


def _process_secret_save(root, revision, value, queue):
    try:
        RuntimeSettings(root).save_secret(revision, "auth.token", value)
        queue.put("saved")
    except ConflictError:
        queue.put("conflict")


def test_secret_process_lock_and_separate_revisions(project):
    service = RuntimeSettings(project)
    runtime_revision = service.snapshot()["revision"]
    credentials_revision = service.secret_snapshot()["revision"]
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    processes = [
        context.Process(target=_process_secret_save, args=(project, credentials_revision, value, queue))
        for value in ("synthetic-one", "synthetic-two")
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=2) for _ in processes) == ["conflict", "saved"]
    assert service.snapshot()["revision"] == runtime_revision
    service.save(runtime_revision, {"http.request_timeout": 42})
    assert {r["path"]: r for r in service.secret_snapshot()["rows"]}["auth.token"]["configured"]
