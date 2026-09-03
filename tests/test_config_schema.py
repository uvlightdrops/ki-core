from pathlib import Path

from ki_core.config import Config


def test_from_yaml_reads_schema_first_sections(tmp_path: Path) -> None:
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
knowledge:
  data_root: "/data/knowledge"
  cache_db: "cache.sqlite"
  graph_db: "graph.sqlite"
  embed_model: "embed-x"
  paths:
    markdown_root: "/data/knowledge/md"
infosite:
  enabled: true
  title: "Knowledge Portal"
  output_base_dir: "/tmp/out"
  domain: "team"
storage:
  cache_dir: "/tmp/cache"
  session_dir: "/tmp/sessions"
  history_dir: "/tmp/history"
http:
  request_timeout: 45
  verify_ssl: false
apps:
  kicli:
    workspace_root: "/workspace"
    prompt_history_dir: "/tmp/history"
    context:
      max_files: 12
      max_size_mb: 7
      relevance_threshold: 0.3
      cache_enabled: false
      cache_ttl_hours: 6
      cache_max_size_mb: 33
      ignore_patterns: ".git,node_modules"
    diff:
      context_lines: 5
      format: "inline"
      highlight_syntax: false
      auto_apply_threshold: 0.6
      max_file_size_kb: 256
""".strip(),
        encoding="utf-8",
    )

    config = Config.from_yaml(config_path)

    assert config.ki_base_url == "https://ki.example.com"
    assert config.ki_api_key == "ki-secret"
    assert config.ki_model == "gpt-like"
    assert config.openai_api_key == "openai-secret"
    assert config.openai_base_url == "https://api.openai.example/v1"
    assert config.openai_model == "gpt-4.1"
    assert config.knowledge_data_root == "/data/knowledge"
    assert config.knowledge_cache_db == "cache.sqlite"
    assert config.knowledge_graph_db == "graph.sqlite"
    assert config.knowledge_embed_model == "embed-x"
    assert config.infosite_enabled is True
    assert config.infosite_title == "Knowledge Portal"
    assert config.infosite_output_base_dir == "/tmp/out"
    assert config.infosite_domain == "team"
    assert config.request_timeout == 45
    assert config.http_verify_ssl is False
    assert config.kicli_cache_dir == "/tmp/cache"
    assert config.kicli_session_dir == "/tmp/sessions"
    assert config.kicli_chat_history_dir == "/tmp/history"
    assert config.kicli_allowed_base_path == "/workspace"
    assert config.context_max_files == 12
    assert config.context_max_size_mb == 7
    assert config.context_relevance_threshold == 0.3
    assert config.context_cache_enabled is False
    assert config.context_cache_ttl_hours == 6
    assert config.context_cache_max_size_mb == 33
    assert config.context_ignore_patterns == ".git,node_modules"
    assert config.diff_context_lines == 5
    assert config.diff_format == "inline"
    assert config.diff_highlight_syntax is False
    assert config.diff_auto_apply_threshold == 0.6
    assert config.diff_max_file_size_kb == 256


def test_from_yaml_rejects_schema_mismatch(tmp_path: Path) -> None:
    config_path = tmp_path / "ki.yaml"
    config_path.write_text(
        """
storage:
  cache_dir: 42
""".strip(),
        encoding="utf-8",
    )

    try:
        Config.from_yaml(config_path)
    except ValueError as exc:
        assert "storage.cache_dir" in str(exc)
    else:
        raise AssertionError("Expected schema validation to fail")
