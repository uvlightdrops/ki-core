# ki-core Configuration Guide

## Overview

ki-core is the shared configuration and LLM provider abstraction for the ki ecosystem.
All projects (ki-knowledge, kicli-code-assist) use the same configuration system.

## Configuration Files

Configuration is loaded in this priority order:

1. **Environment Variables** (highest priority)
2. **`ki.yaml`** (local config, non-sensitive)
3. **`creds.yaml`** (global credentials, gitignored)
4. **Defaults** (lowest priority)

### Location Search Order

ki-core looks for config files in these locations:

```
./ki.yaml
./kicli.yaml
./config.yaml
./config/ki.yaml
./config/config.yaml
~/.config/ki/config.yaml
~/.config/kicli/config.yaml
```

## Setup

### 1. Copy Example Config

```bash
cp ki.yaml.example ki.yaml
```

### 2. Create Credentials File (Optional)

For security, keep API keys separate:

```bash
cat > creds.yaml << 'EOF'
ki:
  base_url: "https://ki.company.com"
  api_key: "your-api-key-here"

openai:
  api_key: "sk-..."
EOF

chmod 600 creds.yaml
git add .gitignore  # Ensure creds.yaml is ignored
```

### 3. Set Environment Variables (Alternative)

```bash
export KI_BASE_URL="https://ki.company.com"
export KI_API_KEY="your-api-key"
export KI_MODEL="google/gemma-4-26B-A4B-it"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.2"
```

## Configuration Sections

### `ki` - Company KI Server

```yaml
ki:
  base_url: "https://ki.company.com"     # Keep in creds.yaml
  api_key: "..."                         # Keep in creds.yaml
  model: "google/gemma-4-26B-A4B-it"     # Model name
  endpoint: "/google/nimservice-..."     # Optional explicit endpoint
```

**Environment Variables:**
```bash
KI_BASE_URL="https://ki.company.com"
KI_API_KEY="..."
KI_MODEL="google/gemma-4-26B-A4B-it"
KI_ENDPOINT="/path/to/endpoint"
```

### `ollama` - Local Inference

```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "llama3.2"
```

**Environment Variables:**
```bash
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="llama3.2"
```

### `openai` - OpenAI or Compatible API

```yaml
openai:
  base_url: "https://api.openai.com/v1"
  model: "gpt-4"
  api_key: "sk-..."                      # Keep in creds.yaml
```

**Environment Variables:**
```bash
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4"
OPENAI_API_KEY="sk-..."
```

### `knowledge` - Knowledge Base Settings

```yaml
knowledge:
  data_root: "~/dev_data/kicli"
  cache_db: "~/.cache/ki/cache.db"
  graph_db: "~/.cache/ki/graph.db"
  embed_model: "nomic-embed-text"
```

**Environment Variables:**
```bash
KNOWLEDGE_DATA_ROOT="~/dev_data/kicli"
KNOWLEDGE_CACHE_DB="~/.cache/ki/cache.db"
KNOWLEDGE_GRAPH_DB="~/.cache/ki/graph.db"
KNOWLEDGE_EMBED_MODEL="nomic-embed-text"
```

### `http` - HTTP Client Settings

```yaml
http:
  request_timeout: 30
  verify_ssl: true
```

**Environment Variables:**
```bash
KI_REQUEST_TIMEOUT="30"
KI_VERIFY_SSL="true"
```

## Usage in Code

### Load Configuration

```python
from ki_core import Config

# Load from YAML + environment
config = Config.from_env()

# Or explicit path
config = Config.from_yaml("./config/prod.yaml")
```

### Use with Providers

```python
from ki_core import Config
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient

config = Config.from_env()

# Use Ollama
ollama_client = OllamaClient(
    base_url=config.ollama_base_url,
    model=config.ollama_model
)

# Use OpenAI
openai_client = OpenAICompatibleClient(
    base_url=config.openai_base_url,
    api_key=config.openai_api_key,
    model=config.openai_model
)
```

## Examples

### Example 1: Local Development with Ollama

**ki.yaml:**
```yaml
ollama:
  base_url: "http://localhost:11434"
  model: "mistral"
```

**Usage:**
```bash
ollama serve
# In another terminal:
ki-chat ollama
```

### Example 2: Production with Company KI Server

**ki.yaml:**
```yaml
ki:
  model: "google/gemma-4-26B-A4B-it"
http:
  request_timeout: 60
```

**creds.yaml:**
```yaml
ki:
  base_url: "https://ki.company.com"
  api_key: "prod-key-xxx"
```

**Usage:**
```bash
ki-chat openai
# Uses config from ki.yaml + creds.yaml
```

### Example 3: Using Knowledge Base

**ki.yaml:**
```yaml
knowledge:
  data_root: "~/dev_data/kicli"
  embed_model: "nomic-embed-text"

ollama:
  base_url: "http://localhost:11434"
  model: "mistral"
```

**Usage:**
```python
from ki_core import Config

config = Config.from_env()
data_path = config.knowledge_data_root
embed_model = config.knowledge_embed_model
# Use in ki-knowledge
```

## Security Best Practices

1. **Keep credentials in `creds.yaml`** - Not in `ki.yaml`
2. **Add `creds.yaml` to `.gitignore`**
3. **Use environment variables for CI/CD**
4. **Restrict file permissions**: `chmod 600 creds.yaml`

### `kicli` - KI CLI / Code Assistant Settings

```yaml
kicli:
  cache_dir: "~/dev_data/kicli-code-assist"
  session_dir: "~/dev_data/kicli-code-assist/sessions"
  chat_history_dir: "~/dev_data/kicli-code-assist/chat_history"
```

**Environment Variables:**
```bash
KICLI_CACHE_DIR="~/dev_data/kicli-code-assist"
KICLI_SESSION_DIR="~/dev_data/kicli-code-assist/sessions"
KICLI_CHAT_HISTORY_DIR="~/dev_data/kicli-code-assist/chat_history"
```

**Usage in kicli-code-assist:**
```python
from ki_core import Config

config = Config.from_env()
cache_dir = config.kicli_cache_dir
chat_history_dir = config.kicli_chat_history_dir
```

### Check Loaded Configuration

```bash
python3 -c "
from ki_core import Config
cfg = Config.from_env()
print(f'Ollama: {cfg.ollama_base_url}')
print(f'Model: {cfg.ollama_model}')
print(f'Timeout: {cfg.request_timeout}')
"
```

### Check Config File Locations

```bash
# See which config files were found
find ~/.config/ki -name "*.yaml" 2>/dev/null
find . -name "ki.yaml" -o -name "creds.yaml"
```
