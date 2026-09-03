# ki-core Configuration Guide

## Overview

`ki-core` resolves configuration in layers and exposes the result through the typed `Config` dataclass.

The merge model is:

1. base config file
2. `config/defaults/*.yaml`
3. `config/profiles/*.yaml`
4. `config/stages/*.yaml`
5. `config/runtime/runtime.yaml`
6. environment variables

Later layers win.

Credentials remain separate in `creds.yaml` and are merged by `ki-core` on top of the YAML config for secret-bearing fields.

## Base config search order

When you call `Config.from_env()` or `Config.from_yaml()` without a fully layered setup, `ki-core` first looks for a base config file in:

```text
./ki.yaml
./kicli.yaml
./config.yaml
./.ki.yaml
./.kicli.yaml
./config/ki.yaml
./config/config.yaml
./config/dev.yaml
./config/prod.yaml
~/.config/ki/config.yaml
~/.config/kicli/config.yaml
```

If a base file is found, `ki-core` also looks for sibling layered config directories beneath that file's directory:

```text
config/defaults/
config/profiles/
config/stages/
config/runtime/runtime.yaml
```

## Credentials search order

Secrets are resolved separately from:

```text
./creds.yaml
./config/creds.yaml
~/.config/ki/creds.yaml
~/.config/kicli/creds.yaml
```

If an explicit config file path is passed, `ki-core` also checks that file's directory for `creds.yaml` and `config/creds.yaml`.

## Recommended layout

For layered projects, prefer:

```text
project/
├── ki.yaml
├── creds.yaml
└── config/
    ├── defaults/
    ├── profiles/
    ├── stages/
    └── runtime/
        └── runtime.yaml
```

Use `ki.yaml` as the base shared entrypoint and place project-specific overlays in `config/`.

## Supported config sections

## `ki`

```yaml
ki:
  base_url: "https://ki.company.com"
  api_key: ""
  model: "google/gemma-4-26B-A4B-it"
  endpoint: ""
```

Env:

```bash
KI_BASE_URL=
KI_API_KEY=
KI_MODEL=
KI_ENDPOINT=
```

## `ollama`

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "llama3.2"
```

Env:

```bash
OLLAMA_BASE_URL=
OLLAMA_MODEL=
```

## `openai`

```yaml
openai:
  base_url: "https://api.openai.com/v1"
  model: "gpt-4"
  api_key: ""
```

Env:

```bash
OPENAI_BASE_URL=
OPENAI_MODEL=
OPENAI_API_KEY=
```

## `knowledge`

```yaml
knowledge:
  data_root: "~/dev_data/ki"
  cache_db: "~/.cache/ki/cache.db"
  graph_db: "~/.cache/ki/graph.db"
  embed_model: "nomic-embed-text"
```

Env:

```bash
KNOWLEDGE_DATA_ROOT=
KNOWLEDGE_CACHE_DB=
KNOWLEDGE_GRAPH_DB=
KNOWLEDGE_EMBED_MODEL=
```

## `http`

```yaml
http:
  request_timeout: 30
  verify_ssl: true
```

Env:

```bash
KI_REQUEST_TIMEOUT=
KI_VERIFY_SSL=
```

## `kicli`

```yaml
kicli:
  cache_dir: "~/dev_data/kicli-code-assist"
  session_dir: "~/dev_data/kicli-code-assist/session"
  chat_history_dir: "~/dev_data/kicli-code-assist/chat_history"
  allowed_base_path: "/path/to/workspace"
```

Env:

```bash
KICLI_CACHE_DIR=
KICLI_SESSION_DIR=
KICLI_CHAT_HISTORY_DIR=
KICLI_ALLOWED_BASE_PATH=
```

## `context`

```yaml
context:
  max_files: 10
  max_size_mb: 5
  relevance_threshold: 0.5
  cache_enabled: true
  cache_ttl_hours: 24
  cache_max_size_mb: 50
  ignore_patterns: "__pycache__,*.pyc,node_modules,.git,.env"
```

## `diff`

```yaml
diff:
  context_lines: 3
  format: "unified"
  highlight_syntax: true
  auto_apply_threshold: 0.8
  max_file_size_kb: 100
```

## Usage

```python
from ki_core import Config

config = Config.from_env()
```

Or with an explicit base file:

```python
from ki_core import Config

config = Config.from_yaml("/path/to/project/ki.yaml")
```

In both cases, sibling layered config under `config/` is included automatically.

## Notes

- `Config` still exposes flat Python attributes like `config.kicli_cache_dir`.
- YAML may use sectioned keys like `kicli.cache_dir`.
- Legacy top-level keys like `kicli_cache_dir` are still read for compatibility.
- Environment variables remain the final override layer.
- Keep secrets in `creds.yaml`, not in `ki.yaml`.
