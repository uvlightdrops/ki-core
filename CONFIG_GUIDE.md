# KI Ecosystem Configuration Guide

## Overview

The KI ecosystem uses **schema-based configuration management** with layered resolution. All configuration defaults are defined in JSON Schema files, not in code. This eliminates code-based fallbacks and provides a single source of truth.

### Configuration Resolution Order (high to low priority)

1. **Environment variables** (`KI_CFG_*` prefix)
2. **Runtime files** (`config/runtime/runtime.yaml`)
3. **Stages** (`config/stages/*.yaml`) - e.g., dev/prod/test environments
4. **Profiles** (`config/profiles/*.yaml`) - e.g., different setups
5. **Defaults** (`config/defaults/*.yaml`) - default values per domain
6. **Main config** (`ki.yaml`) - project base config
7. **Schema defaults** - final fallback from JSON Schema

Later layers override earlier ones. This allows for flexible, environment-aware configuration.

**Credentials** (`creds.yaml`) are kept separate for security and merged into the resolved config.

## Schema Structure

### Base Schema (ki-core)

```
ki-core/
  schema/
    config.schema.yaml          # Base schema with all common settings
```

### App-Specific Schemas

```
kicli-code-assist/
  schema/
    kicli.schema.yaml           # kicli-specific settings
```

Schemas are merged automatically when loading config, allowing each app to extend the base schema.

## Configuration Files

### Main Config: `ki.yaml`

Non-sensitive configuration and application settings:

```yaml
llm:
  default_provider: "ki"
  providers:
    ki:
      base_url: "https://api.example.com/v1"
      model: "google/gemma-4-26B-A4B-it"
    ollama:
      base_url: "http://localhost:11434"
      model: "llama3.2"
    openai:
      base_url: "https://api.openai.com/v1"
      model: "gpt-4"

apps:
  kicli:
    workspace_root: ""
    context:
      max_files: 10
      cache_enabled: true
```

### Credentials: `creds.yaml`

**Security:** Kept separate from `ki.yaml`, not committed to version control.

```yaml
creds:
  llm:
    providers:
      ki:
        api_key: "your-api-key"
      openai:
        api_key: "sk-..."
```

Place in one of these locations:
- `./creds.yaml`
- `./config/creds.yaml`
- `~/.config/ki/creds.yaml`
- `~/.config/kicli/creds.yaml`

### Layered Config Structure

For complex setups, organize config by layers:

```
config/
  defaults/
    llm.yaml          # Default LLM settings
    storage.yaml      # Default storage paths
  profiles/
    local.yaml        # Local development profile
    docker.yaml       # Docker profile
  stages/
    dev.yaml          # Development overrides
    prod.yaml         # Production overrides
  runtime/
    runtime.yaml      # Generated at runtime (e.g., auto-detected paths)
```

Example `config/profiles/local.yaml`:
```yaml
apps:
  kicli:
    context:
      cache_enabled: false      # Disable caching in dev
```

Example `config/stages/dev.yaml`:
```yaml
http:
  verify_ssl: false             # Allow self-signed certs in dev
```

## Environment Variables

Override any config value using environment variables with the `KI_CFG_` prefix:

```bash
# Use underscores for nested keys
export KI_CFG_LLM__DEFAULT_PROVIDER=openai
export KI_CFG_APPS__KICLI__CONTEXT__MAX_FILES=20
export KI_CFG_APPS__KICLI__WORKSPACE_ROOT=/home/user/projects

# String values
export KI_CFG_LLM__PROVIDERS__OLLAMA__BASE_URL=http://localhost:11434

# Boolean values
export KI_CFG_APPS__KICLI__CONTEXT__CACHE_ENABLED=true

# Integer values
export KI_CFG_APPS__KICLI__CONTEXT__CACHE_TTL_HOURS=48
```

## Config Generation

### Generate Config Skeleton

To generate a config skeleton with all available options and defaults:

**From ki-core:**
```bash
ki-chat config-skeleton ./ki.yaml
```

**From kicli-code-assist:**
```bash
kicli-assist config init -o ./ki.yaml
```

This generates a complete YAML file with all schema-defined options and their default values.

## Configuration Sections

### LLM Configuration

```yaml
llm:
  default_provider: "ki"              # Active provider
  providers:
    ki:                               # Company KI server
      base_url: ""
      api_key: ""                     # Set in creds.yaml
      model: "google/gemma-4-26B-A4B-it"
      endpoint: ""
    
    ollama:                           # Local Ollama instance
      base_url: "http://localhost:11434"
      model: "llama3.2"
    
    openai:                           # OpenAI or compatible
      base_url: "https://api.openai.com/v1"
      api_key: ""                     # Set in creds.yaml
      model: "gpt-4"
```

### Knowledge Base

```yaml
knowledge:
  data_root: ""                       # e.g., ~/dev_data/kicli
  cache_db: ""                        # Optional: custom cache location
  graph_db: ""                        # Optional: custom graph db
  embed_model: "nomic-embed-text"    # Embedding model
  default_domain: "default"
```

### Storage

```yaml
storage:
  cache_dir: "~/.cache/ki"
  session_dir: "~/.cache/ki/sessions"
  history_dir: "~/.cache/ki/chat_history"
```

### KI CLI / kicli-code-assist

```yaml
apps:
  kicli:
    workspace_root: ""                # Workspace analysis root
    prompt_history_dir: ""            # Prompt storage
    
    context:                          # Context system
      max_files: 10                   # Max files in context
      max_size_mb: 5                  # Max total size (MB)
      relevance_threshold: 0.15       # Min relevance (0-1)
      cache_enabled: true
      cache_ttl_hours: 24
      cache_max_size_mb: 50
      ignore_patterns: "__pycache__,*.pyc,node_modules,.git,.env"
    
    diff:                             # Diff engine
      context_lines: 3                # Context lines around changes
      format: "unified"               # Format type
      highlight_syntax: true
      auto_apply_threshold: 0.8       # Auto-apply confidence (0-1)
      max_file_size_kb: 100
```

## Schema Validation

All loaded config is validated against the merged JSON Schema. Validation errors show the path and problem:

```
Schema validation failed:
llm.providers.ki.base_url: 'extra fields not permitted'
```

## Python API

### Load config from YAML

```python
from ki_core import Config

# Auto-discover ki.yaml in standard locations
config = Config.from_yaml()

# Or specify explicit path
config = Config.from_yaml("./config/dev.yaml")

# Or load from environment variables only
config = Config.from_env()
```

### Access config values

```python
# Typed access - all values are validated
print(config.ki_base_url)
print(config.context_max_files)  # int
print(config.context_cache_enabled)  # bool
```

All fields are type-safe. See the `Config` dataclass for all available fields.

## Migration from Legacy Format

**Old (legacy) format** - still supported for backward compatibility:

```yaml
# ❌ Don't use these anymore
ki:
  base_url: ""
  api_key: ""
  model: ""

context:
  max_files: 10

diff:
  context_lines: 3
```

**New (canonical) format** - use this:

```yaml
# ✅ Use this format
llm:
  providers:
    ki:
      base_url: ""
      api_key: ""
      model: ""

apps:
  kicli:
    context:
      max_files: 10
    diff:
      context_lines: 3
```

Both work currently, but legacy format will be removed in a future version. Migrate existing configs using:

```bash
# Generate new config skeleton
ki-chat config-skeleton ./ki-new.yaml

# Manually migrate custom values
```

## Examples

See `ki.yaml.example` for a complete working example with all options documented.

## Troubleshooting

### Config not loading

1. Check file locations - see "Base config search order" above
2. Validate YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('ki.yaml'))"`
3. Check schema validation: Look for `KI_CFG_DISABLED_` env var prefix (enables logging)

### Values not applying

1. Check resolution order - later layers override earlier ones
2. Use `kicli-assist doctor` or `ki-chat help` to see active config
3. Verify environment variable syntax (`KI_CFG_*` prefix, `__` for nesting)

### Credentials not found

1. Ensure `creds.yaml` exists in one of the search locations
2. Check permissions: `chmod 600 creds.yaml` (only you should read it)
3. Path must be in same directory or parent of `ki.yaml`
