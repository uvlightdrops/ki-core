# Getting Started with ki-core

Welcome to ki-core – the unified LLM provider abstraction for the ki ecosystem.

## What is ki-core?

ki-core provides:
- **Unified AIClient interface** for different LLM providers
- **Provider implementations**: OpenAI, Ollama (local), Mock (testing)
- **Shared configuration system** (YAML + environment variables)
- **CLI tool** (`ki-chat`) for quick testing
- **Models & error handling** for all providers

## Quick Start (2 minutes)

### 1. Install ki-core

```bash
pip install ki-core
```

Or for development:

```bash
cd /home/flow/dev_flow/ki-core
pip install -e .
```

### 2. Choose a Provider

#### Option A: Mock (no setup needed)

```bash
ki-chat mock
# "Hello" → "mock:Hello"
```

#### Option B: Ollama (local, free)

```bash
# Start Ollama in another terminal
ollama serve

# Then chat
ki-chat ollama
```

#### Option C: OpenAI API

```bash
export KI_API_KEY=sk-...
ki-chat openai
```

### 3. Use in Code

```python
from ki_core import Config
from ki_core.adapters.ollama import OllamaClient
from ki_core.core.models import ChatRequest, Message, Role

# Load config
config = Config.from_env()

# Create client
client = OllamaClient(
    base_url=config.ollama_base_url,
    model=config.ollama_model
)

# Chat
request = ChatRequest(
    messages=[Message(role=Role.USER, content="Hello")]
)

# Non-streaming
response = client.chat(request)
print(response.message.content)

# Or streaming
for event in client.chat_stream(request):
    if event.text:
        print(event.text, end="", flush=True)
```

## Configuration

See [`CONFIG_GUIDE.md`](../CONFIG_GUIDE.md) for detailed setup.

### Quick Setup

```bash
# Copy example config
cp ki.yaml.example ki.yaml

# Edit with your settings
vi ki.yaml

# (Optional) Create credentials file
cat > creds.yaml << 'CREDS'
ki:
  base_url: "https://ki.company.com"
  api_key: "your-api-key"
CREDS
chmod 600 creds.yaml
```

## Available Providers

### MockAIClient (Testing)

```python
from ki_core.adapters.mock import MockAIClient

client = MockAIClient()
response = client.chat(request)
# Always returns: "mock:<user_content>"
```

**Use when:** Testing without external dependencies

### OllamaClient (Local)

```python
from ki_core.adapters.ollama import OllamaClient

client = OllamaClient(
    base_url="http://localhost:11434",
    model="llama3.2"
)
```

**Setup:**
```bash
ollama serve  # Start in another terminal
ollama pull llama3.2  # Download model
```

**Use when:** Local development, no API costs, privacy needed

### OpenAICompatibleClient (Cloud/API)

```python
from ki_core.adapters.openai_compat import OpenAICompatibleClient

# OpenAI
client = OpenAICompatibleClient(
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    model="gpt-4"
)

# Or Azure
client = OpenAICompatibleClient(
    base_url="https://your-resource.openai.azure.com/",
    api_key="your-azure-key",
    model="deployment-name"
)

# Or vLLM
client = OpenAICompatibleClient(
    base_url="http://localhost:8000/v1",
    api_key="any-key",
    model="llama2"
)
```

**Use when:** Production, need specific models, have API access

## Common Tasks

### Switch Providers Easily

```python
from ki_core import Config

config = Config.from_env()

# Auto-select based on config
if config.ki_api_key:
    # Use company server
    client = OpenAICompatibleClient(
        base_url=config.ki_base_url,
        api_key=config.ki_api_key,
        model=config.ki_model
    )
elif config.ollama_base_url:
    # Use local Ollama
    client = OllamaClient(
        base_url=config.ollama_base_url,
        model=config.ollama_model
    )
```

### Stream Responses

All providers support streaming:

```python
for event in client.chat_stream(request):
    if event.type.value == "token":
        print(event.text, end="", flush=True)
    elif event.type.value == "done":
        break
```

### Handle Errors

```python
from ki_core.core.errors import (
    AIError, AuthError, ProviderError, TimeoutError
)

try:
    response = client.chat(request)
except AuthError as e:
    print(f"Authentication failed: {e}")
except TimeoutError as e:
    print(f"Request timed out: {e}")
except ProviderError as e:
    print(f"Provider error: {e}")
```

## CLI Tool: ki-chat

### Commands

```bash
ki-chat mock              # Test mode (no deps)
ki-chat ollama            # Chat with local Ollama
ki-chat openai            # Chat with OpenAI API
ki-chat help              # Show help
```

### Examples

```bash
# Interactive chat with Ollama
ki-chat ollama
> You: What is machine learning?
> Assistant: Machine learning is...

# Set model via env
OLLAMA_MODEL=mistral ki-chat ollama

# Use OpenAI
KI_API_KEY=sk-... ki-chat openai
```

## Integration with Other Projects

ki-core is used by:

- **ki-knowledge**: Knowledge base + RAG system
- **kicli-code-assist**: Code generation and review tool
- Your custom projects

All use the same `Config` system and providers.

## Next Steps

1. **Read the config guide**: [`CONFIG_GUIDE.md`](../CONFIG_GUIDE.md)
2. **Run your first chat**: `ki-chat mock`
3. **Set up your provider**: Ollama or OpenAI
4. **Use in your project**: `from ki_core import Config, AIClient`
5. **Explore adapters**: See `src/ki_core/adapters/` for implementations

## Troubleshooting

**"ki-chat: command not found"**
→ Install with: `pip install -e .` (from ki-core directory)

**"Connection refused" (Ollama)**
→ Start Ollama first: `ollama serve`

**"Invalid API key" (OpenAI)**
→ Check `KI_API_KEY` environment variable

**"No models available" (Ollama)**
→ Download a model: `ollama pull llama3.2`

## Documentation

- [`CONFIG_GUIDE.md`](../CONFIG_GUIDE.md) - Configuration reference
- [`README.md`](../README.md) - Project overview
- `src/ki_core/core/models.py` - Data models
- `src/ki_core/adapters/` - Provider implementations

## Support

Need help?
- Check documentation in `docs/`
- Look at examples in `src/ki_core/cli.py`
- Review provider implementations in `src/ki_core/adapters/`
