# ki-core

Shared Python AI client abstraction layer for `ki-knowledge`, `kicli-code-assist`, and other projects.

Provides unified LLM provider access, configuration management, and CLI tools.

## Features

- ✅ **Unified AIClient interface** – single abstraction for all LLM providers
- ✅ **Multiple adapters** – OpenAI, Ollama (local), Mock (testing)
- ✅ **Shared configuration** – layered YAML + credentials + environment variables
- ✅ **CLI tool** – `ki-chat` for quick testing
- ✅ **Streaming support** – all providers support token streaming
- ✅ **Error handling** – specific exceptions for different error types

## Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** – Quick start with any provider
- **[Configuration Guide](CONFIG_GUIDE.md)** – layered config, credentials, environment variables
- **[Provider Reference](#providers)** – Details on each provider


## Quick start

```bash
cd /home/flow/dev_flow/ki-core
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Use with Mock Provider (for testing)
```bash
python3 -c "
from ki_core.adapters.mock import MockAIClient
from ki_core.core.models import ChatRequest, Message, Role

client = MockAIClient()
request = ChatRequest(messages=[Message(role=Role.USER, content='Hello')])
response = client.chat(request)
print(response.message.content)
"
```

### Use with Ollama (local inference)
```bash
# Start Ollama (separate terminal)
ollama serve

# In another terminal
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama2
python3 -m ki_core.cli ollama
```

### Use with OpenAI API
```bash
export KI_API_KEY=sk-...
export KI_BASE_URL=https://api.openai.com/v1
export KI_MODEL=gpt-4
python3 -m ki_core.cli openai
```

### CLI Commands
```bash
ki-chat mock                 # Test with mock (no API needed)
ki-chat ollama               # Local inference with Ollama
ki-chat openai               # Cloud API (OpenAI, Azure, etc.)
ki-chat help                 # Show help
```

## Adapter Implementations

### Available Providers

| Provider | Use Case | Authentication |
|----------|----------|-----------------|
| **MockAIClient** | Testing, development | None |
| **OllamaClient** | Local inference (faster, free) | None |
| **OpenAICompatibleClient** | Cloud APIs (OpenAI, Azure, vLLM) | API Key |

### Example: Chat Interface

```python
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.core.models import ChatRequest, Message, Role

# Initialize client
client = OpenAICompatibleClient(
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    model="gpt-4",
)

# Streaming chat
request = ChatRequest(
    messages=[
        Message(role=Role.SYSTEM, content="You are a helpful assistant."),
        Message(role=Role.USER, content="Explain quantum computing."),
    ]
)

for event in client.chat_stream(request):
    if event.text:
        print(event.text, end="", flush=True)
```

## Integration with kicli-code-assist and ki-knowledge

Both projects now use ki-core for unified LLM access:

```bash
# Both projects require Python 3.10+ and use ki-core adapters
pip install kicli-code-assist    # Uses ki-core for AI
pip install ki-knowledge         # Uses ki-core for AI
```

## Adapter contract

Implement `AIClient`:

- `chat(request: ChatRequest) -> ChatResponse`
- `chat_stream(request: ChatRequest) -> Iterator[StreamEvent]`

## Versioning

`0.1.0a1` initializes the core contract for parallel integration in both projects.
