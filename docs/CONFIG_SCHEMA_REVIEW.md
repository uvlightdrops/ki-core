# Config schema review

**Status: Implemented.** `knowledge`, `jira`, `infosite`, and
`apps.ki_knowledge.*` have been moved out of ki-core into
`ki-knowledge/schema/ki_knowledge.schema.yaml`; `security`, `prompts` and
`storage` have been moved into
`kicli-code-assist/schema/kicli.schema.yaml`. ki-core's own schema
(`ki-core/src/ki_core/schema/config.schema.yaml`, the single source of
truth - the old root-level `ki-core/schema/config.schema.yaml` duplicate
was removed) now only contains truly generic sections (`llm`, `http`,
`creds`, `apps` namespace). The `ki_core.Config` dataclass described below
as a "shared typed projection" has also been removed entirely - each app
now builds its own thin config accessor on top of `ki_core.load_config()`.
The rest of this document is kept for historical context.

This document defines the intended naming and scope model for the shared `ki-*` configuration family.

## Goal

Use one coherent schema model across:

- `yaml_cfg_wizard` as the layered resolver and validator
- `ki-core` as the shared typed projection and env bridge
- `kicli-code-assist` as one consuming app
- `ki-knowledge` as another consuming app

The schema should describe stable domains, not historical implementation details.

## Current problems

The current config family mixes several concerns:

| Problem | Example |
| --- | --- |
| Product-specific prefixes leak into unrelated apps | `KICLI_DATA_ROOT` inside `ki-knowledge` |
| Same concern is named differently by layer | YAML `knowledge.data_root` vs env `KICLI_DATA_ROOT` |
| Provider scope and platform scope are mixed | `KI_*`, `OPENAI_*`, `OLLAMA_*` |
| Generic runtime settings live beside app-specific ones without a clear namespace rule | `http.verify_ssl`, `kicli.chat_history_dir`, `jira.csv_path` |
| Legacy env names encode old project ownership rather than domain ownership | `KICLI_MD_ROOT`, `KICLI_PDF_ROOT` |

## Recommended scope model

The top-level YAML sections should represent **domains of responsibility**:

```text
llm
knowledge
storage
http
jira
infosite
apps
```

### 1. `llm`

All language-model provider settings belong under one shared scope.

```yaml
llm:
  default_provider: "ollama"
  providers:
    ki:
      base_url: "https://ki.company.com"
      api_key: ""
      model: "google/gemma-4-26B-A4B-it"
      endpoint: ""
    openai:
      base_url: "https://api.openai.com/v1"
      api_key: ""
      model: "gpt-4"
    ollama:
      base_url: "http://localhost:11434"
      model: "llama3.2"
```

Why:

- the concern is “LLM runtime”, not three unrelated top-level systems
- provider-specific settings stay grouped, while app code can still project convenience fields
- this leaves room for future providers without growing the YAML root endlessly

### 2. `knowledge`

Knowledge-domain behavior should live here, not under app names.

```yaml
knowledge:
  data_root: "~/dev_data/ki"
  cache_db: "~/.cache/ki/cache.db"
  graph_db: "~/.cache/ki/graph.db"
  embed_model: "nomic-embed-text"
  default_domain: "default"
  paths:
    markdown_root: ""
    jira_root: ""
    ontology_root: ""
    pdf_root: ""
```

Why:

- `ki-knowledge` and related tooling use the same underlying data domain
- names like `KICLI_DATA_ROOT` are wrong in a knowledge app
- content-type roots are substructure of knowledge storage, not of `kicli`

### 3. `storage`

Cross-app runtime file storage should be separated from knowledge content storage.

```yaml
storage:
  cache_dir: "~/.cache/ki"
  session_dir: "~/.local/state/ki/sessions"
  history_dir: "~/.local/state/ki/history"
```

Why:

- cache/session/history are generic runtime storage concerns
- they should not be tied to `kicli` if the same pattern is reused by other apps

### 4. `http`

Keep transport concerns isolated.

```yaml
http:
  request_timeout: 30
  verify_ssl: true
```

### 5. `jira`

Jira-specific import and analysis settings should live under one dedicated scope.

```yaml
jira:
  url: ""
  username: ""
  api_token: ""
  csv_path: ""
  cache_db: ""
  graph_db: ""
  graph_cypher_path: ""
  csv_delimiter: ""
  csv_encoding: "utf-8-sig"
  timeline_days: 14
  embed_model: ""
  use_hybrid_search: true
  use_graph: true
  cache_refresh: true
```

Why:

- current Jira settings are spread across generic knowledge config plus many ad hoc env vars
- a first-class `jira` section makes ownership clear

### 6. `infosite`

Keep publication/output behavior under its own domain.

```yaml
infosite:
  enabled: false
  title: ""
  output_base_dir: ""
  domain: "default"
```

### 7. `apps`

App-specific UI/runtime preferences belong here, not in shared domain scopes.

```yaml
apps:
  kicli:
    workspace_root: ""
    prompt_history_dir: ""
    context:
      max_files: 10
      max_size_mb: 5
      relevance_threshold: 0.15
      cache_enabled: true
      cache_ttl_hours: 24
      cache_max_size_mb: 50
      ignore_patterns: "__pycache__,*.pyc,node_modules,.git,.env"
    diff:
      context_lines: 3
      format: "unified"
      highlight_syntax: true
      auto_apply_threshold: 0.8
      max_file_size_kb: 100
  ki_knowledge:
    api_url: "http://localhost:8090/api/knowledge"
    django:
      db_path: ""
      secret_key: ""
      debug: true
      allowed_hosts: ["*"]
      wagtail_admin_base_url: "http://localhost:8000"
```

Why:

- this distinguishes shared platform config from app-owned behavior
- `context` and `diff` are not generic ki-platform concepts today; they belong to the assistant app
- Django-specific knobs clearly belong to `ki-knowledge`, not to `ki-core`

## Recommended naming rules

1. Prefer **domain nouns** over project names.
   - Good: `knowledge.data_root`
   - Bad: `kicli_data_root`

2. Prefer **nested YAML scopes** over flat root growth.
   - Good: `apps.kicli.context.max_files`
   - Bad: `context_max_files`

3. Use `*_dir` for directories and `*_path` for files.
   - Good: `storage.cache_dir`, `jira.csv_path`

4. Keep provider names below a provider collection.
   - Good: `llm.providers.ollama.base_url`
   - Bad: root-level `ollama.base_url` if designing from scratch

5. Secrets should stay structurally colocated with their owning scope.
   - Example: `llm.providers.openai.api_key`
   - Example: `jira.api_token`

## Environment variable strategy

The env layer should mirror YAML ownership instead of historical names.

Recommended canonical env pattern:

```text
KI_LLM__DEFAULT_PROVIDER
KI_LLM__PROVIDERS__KI__BASE_URL
KI_LLM__PROVIDERS__OPENAI__API_KEY
KI_KNOWLEDGE__DATA_ROOT
KI_KNOWLEDGE__PATHS__PDF_ROOT
KI_STORAGE__CACHE_DIR
KI_JIRA__CSV_PATH
KI_APPS__KICLI__WORKSPACE_ROOT
KI_APPS__KICLI__CONTEXT__MAX_FILES
KI_APPS__KI_KNOWLEDGE__DJANGO__DEBUG
```

Why:

- this maps directly to the YAML shape
- it avoids maintaining a separate naming taxonomy for env vars
- `yaml_cfg_wizard` already supports nested env mapping via `__`

## Migration guidance

This should be done in phases.

### Phase 1: define canonical schema

- add the new canonical YAML structure to `ki-core/schema/config.schema.yaml`
- document canonical names first
- keep old names working as compatibility input

### Phase 2: add compatibility mapping in `ki-core`

Map legacy fields into the canonical structure, for example:

- `ki.*` -> `llm.providers.ki.*`
- `openai.*` -> `llm.providers.openai.*`
- `ollama.*` -> `llm.providers.ollama.*`
- `kicli.cache_dir` -> `storage.cache_dir`
- `kicli.session_dir` -> `storage.session_dir`
- `kicli.chat_history_dir` -> `storage.history_dir`
- `context.*` -> `apps.kicli.context.*`
- `diff.*` -> `apps.kicli.diff.*`
- `KICLI_DATA_ROOT` -> `knowledge.data_root`
- `KICLI_MD_ROOT` -> `knowledge.paths.markdown_root`
- `KICLI_JIRA_ROOT` -> `knowledge.paths.jira_root`
- `KICLI_OWL_ROOT` -> `knowledge.paths.ontology_root`
- `KICLI_PDF_ROOT` -> `knowledge.paths.pdf_root`

### Phase 3: move app code to canonical access

- `ki-core.Config` can still expose compatibility properties temporarily
- new code should read from canonical scopes or from compatibility accessors that are clearly marked
- docs and examples should stop introducing legacy names

## Immediate recommendation

The most sensible canonical model for the `ki-*` family is:

1. `llm` for providers
2. `knowledge` for knowledge-domain data and embeddings
3. `storage` for generic runtime filesystem state
4. `http` for transport
5. `jira` for Jira integration
6. `infosite` for publication
7. `apps.<app-name>` for app-owned behavior

That gives you a schema that reflects real ownership boundaries and scales better than continuing to grow `ki`, `kicli`, `context`, and `diff` as unrelated root namespaces.
