import os

import pytest

from ki_core.config import _resolve_config, load_config
from ki_core.runtime_settings import resolve_runtime_candidate


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KI_STAGE", raising=False)
    monkeypatch.delenv("KI_PROFILE", raising=False)
    for key in list(os.environ):
        if key.startswith(("KI_CFG_", "APP_")):
            monkeypatch.delenv(key)
    (tmp_path / "ki.yaml").write_text("stack:\n  services:\n    old: {}\n")
    schema = tmp_path / "probe.schema.yaml"
    schema.write_text(
        "type: object\nproperties:\n  stack:\n    type: object\n"
        "    additionalProperties: false\n    properties:\n"
        "      target:\n        type: string\n"
        "      services:\n        type: object\n        properties:\n"
        "          old:\n            type: object\n            default: {}\n",
    )
    monkeypatch.setattr("ki_core.config.get_merged_schemas", lambda start=None: [schema])
    monkeypatch.setattr("ki_core.config._find_creds_yaml_path", lambda path=None: None)
    return tmp_path


def test_stage_replacement_survives_schema_defaults_and_higher_layers(project, monkeypatch):
    stages = project / "config" / "stages"
    stages.mkdir(parents=True)
    (stages / "minimal.yaml").write_text(
        "stack:\n  __replace__: true\n  services:\n    web: {}\n",
    )
    runtime = project / "config" / "runtime"
    runtime.mkdir()
    (runtime / "runtime.yaml").write_text("stack:\n  services:\n    worker: {}\n")
    monkeypatch.setenv("KI_STAGE", "minimal")
    monkeypatch.setenv("KI_CFG_STACK__TARGET", "local")
    assert load_config(project / "ki.yaml")["stack"] == {
        "services": {"web": {}, "worker": {}}, "target": "local",
    }


def test_multiple_defaults_replace_without_resurrecting_schema_entries(project):
    defaults = project / "config" / "defaults"
    defaults.mkdir(parents=True)
    (defaults / "a.yaml").write_text("stack:\n  services:\n    older: {}\n")
    (defaults / "b.yaml").write_text("stack:\n  __replace__: true\n  services: {}\n")
    # A later unmarked layer may explicitly reintroduce values.
    (project / "ki.yaml").write_text("stack:\n  services:\n    new: {}\n")
    assert load_config(project / "ki.yaml")["stack"] == {"services": {"new": {}}}


def test_runtime_candidate_replaces_disk_layer_and_respects_marker(project):
    runtime = project / "config" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.yaml").write_text("stack:\n  services:\n    disk: {}\n")
    candidate = {"stack": {"__replace__": True, "services": {"candidate": {}}}}
    result = resolve_runtime_candidate(project, candidate)
    assert result["stack"] == {"services": {"candidate": {}}}
    assert candidate["stack"]["__replace__"] is True
    # Removing the candidate replacement restores inheritance.
    result = resolve_runtime_candidate(project, {})
    assert result["stack"] == {"target": "", "services": {"old": {}}}


@pytest.mark.parametrize("credentials_file", [False, True])
def test_credentials_replacement_survives_final_merge(project, monkeypatch, credentials_file):
    candidate = {"stack": {"__replace__": True, "services": {"credential": {}}}}
    if credentials_file:
        path = project / "creds.yaml"
        path.write_text(
            "stack:\n  __replace__: true\n  services:\n    credential: {}\n",
        )
        monkeypatch.setattr("ki_core.config._find_creds_yaml_path", lambda config_path=None: path)
        result = _resolve_config(project_root=project)
    else:
        result = _resolve_config(project_root=project, creds_candidate=candidate)
    assert result["stack"] == {"services": {"credential": {}}}


def test_without_marker_schema_defaults_still_fill_missing_entries(project):
    (project / "ki.yaml").write_text("stack:\n  services:\n    new: {}\n")
    assert load_config(project / "ki.yaml")["stack"] == {
        "target": "", "services": {"old": {}, "new": {}},
    }


def test_unmarked_credentials_extend_replaced_runtime_section(project):
    result = _resolve_config(
        project_root=project,
        runtime_candidate={"stack": {"__replace__": True, "services": {}}},
        creds_candidate={"stack": {"services": {"credential": {}}}},
    )
    assert result["stack"] == {"services": {"credential": {}}}
