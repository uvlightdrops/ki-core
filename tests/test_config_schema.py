from pathlib import Path

from ki_core.config import load_config


def test_load_config_reads_generic_base_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "ki.yaml"
    config_path.write_text(
        """
llm:
  default_provider: "openai"
  providers:
    ki:
      base_url: "https://ki.example.com"
      api_key: "ki-secret"
      model: "gpt-like"
    openai:
      api_key: "openai-secret"
      base_url: "https://api.openai.example/v1"
      model: "gpt-4.1"
http:
  request_timeout: 45
  verify_ssl: false
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.get_path("llm.providers.ki.base_url") == "https://ki.example.com"
    assert config.get_path("llm.providers.ki.api_key") == "ki-secret"
    assert config.get_path("llm.providers.ki.model") == "gpt-like"
    assert config.get_path("llm.providers.openai.api_key") == "openai-secret"
    assert config.get_path("llm.providers.openai.base_url") == "https://api.openai.example/v1"
    assert config.get_path("llm.providers.openai.model") == "gpt-4.1"
    assert config.get_path("http.request_timeout") == 45
    assert config.get_path("http.verify_ssl") is False

    # Schema defaults fill in anything not set explicitly.
    assert config.get_path("llm.providers.ollama.base_url") == "http://localhost:11434"
    assert config.get_path("llm.providers.ollama.model") == "llama3.2"


def test_load_config_get_path_returns_default_for_missing_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "ki.yaml"
    config_path.write_text("llm:\n  default_provider: mock\n", encoding="utf-8")

    config = load_config(config_path)

    assert config.get_path("does.not.exist", default="fallback") == "fallback"
    assert config.get_path("does.not.exist") is None


def test_load_config_rejects_schema_mismatch(tmp_path: Path) -> None:
    config_path = tmp_path / "ki.yaml"
    config_path.write_text(
        """
http:
  request_timeout: "not-an-integer"
""".strip(),
        encoding="utf-8",
    )

    try:
        load_config(config_path)
    except ValueError as exc:
        assert "http.request_timeout" in str(exc)
    else:
        raise AssertionError("Expected schema validation to fail")
