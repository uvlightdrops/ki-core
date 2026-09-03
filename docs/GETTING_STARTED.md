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

Create a base config:

```bash
cp ki.yaml.example ki.yaml
```

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

`Config.from_env()` will merge the base file, optional layered YAML, credentials, and environment variables.

## Example

```python
from ki_core import Config
from ki_core.adapters.ollama import OllamaClient

config = Config.from_env()
client = OllamaClient(
    base_url=config.ollama_base_url,
    model=config.ollama_model,
)
```

## Environment overrides

```bash
export KI_API_KEY=...
export KI_BASE_URL=https://api.openai.com/v1
export KI_MODEL=gpt-4
```

See `../CONFIG_GUIDE.md` for full details.
