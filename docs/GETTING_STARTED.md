# Getting Started with ki-core

`ki-core` provides shared AI provider access plus layered configuration for the ki ecosystem.

## Install

```bash
pip install ki-core
```

For local development:

```bash
cd /home/flow/dev_flow/ki-core
pip install -e .
```

## Quick config setup

Generate a base config skeleton with all schema-defined defaults filled in:

```bash
ki-chat config-skeleton ./ki.yaml
```

App-specific settings (e.g. kicli-code-assist, ki-knowledge) are merged in
automatically if that app's own `schema/*.schema.yaml` is discoverable -
each app also provides its own thin wrapper command for this (e.g.
`kicli-assist config init`).

Optional credentials:

```bash
cat > creds.yaml << 'EOF'
ki:
  base_url: "https://ki.company.com"
  api_key: "your-api-key"
EOF
chmod 600 creds.yaml
```

Optional layered overrides:

```text
config/defaults/
config/profiles/
config/stages/
config/runtime/runtime.yaml
```

`load_config()` will merge the base file, optional layered YAML, credentials, environment variables, and schema defaults.

## Example

```python
from ki_core import load_config
from ki_core.adapters.ollama import OllamaClient

config = load_config()
client = OllamaClient(
    base_url=config.get_path("llm.providers.ollama.base_url"),
    model=config.get_path("llm.providers.ollama.model"),
)
```

`load_config()` returns a plain dict (`ConfigDict`) with a convenience
`get_path("a.b.c", default=...)` helper - there is no app-specific
dataclass in ki-core. Each app should build its own thin config
accessor on top of this if it wants attribute-style access (see e.g.
`kicli_code_assist.app_config.AppConfig`).

## Environment overrides

```bash
export KI_API_KEY=...
export KI_BASE_URL=https://api.openai.com/v1
export KI_MODEL=gpt-4
```

See `../CONFIG_GUIDE.md` for full details.
