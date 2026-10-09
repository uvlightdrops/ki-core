import pytest

from ki_core.config import active_layers, load_config


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "ki.yaml").write_text("llm:\n  default_provider: mock\n")
    stages = tmp_path / "config" / "stages"
    stages.mkdir(parents=True)
    (stages / "dev-lokal.yaml").write_text("llm:\n  default_provider: ollama\n")
    (stages / "prod.yaml").write_text("llm:\n  default_provider: ki\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KI_STAGE", raising=False)
    monkeypatch.delenv("KI_PROFILE", raising=False)
    return tmp_path


def test_no_stage_selected_loads_no_stage(project):
    assert load_config().get_path("llm.default_provider") == "mock"
    assert active_layers()["stage"] is None


def test_marker_selects_exactly_one_stage(project):
    (project / "config" / "stages" / ".active_stage").write_text("dev-lokal\n")
    assert load_config().get_path("llm.default_provider") == "ollama"
    assert active_layers()["stage"] == "dev-lokal"


def test_env_wins_over_marker(project, monkeypatch):
    (project / "config" / "stages" / ".active_stage").write_text("dev-lokal\n")
    monkeypatch.setenv("KI_STAGE", "prod")
    assert load_config().get_path("llm.default_provider") == "ki"


def test_unknown_stage_fails(project, monkeypatch):
    monkeypatch.setenv("KI_STAGE", "nope")
    with pytest.raises(ValueError, match="available: dev-lokal, prod"):
        load_config()
