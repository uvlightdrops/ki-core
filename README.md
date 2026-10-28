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
- **[Configuration Guide](CONFIG_GUIDE.md)** – links to canonical YAML operation and design
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

### Configuration-driven client factory

Applications should use the shared factory rather than duplicate provider
selection and adapter construction:

```python
from ki_core import ConfigManager, ChatRequest, Message, Role
from ki_core import create_chat_client, get_chat_models, get_chat_settings

manager = ConfigManager()
settings = get_chat_settings(manager)  # No provider probes; "auto" stays "auto".
client = create_chat_client(manager)   # Resolves "auto" through ConfigManager.
response = client.chat(ChatRequest([Message(Role.USER, "Hello")]))
print(response.message.content)
```

`llm.provider` selects `ki`, `openai`, `ollama`, `mock`, or `auto`. The factory
uses `llm.providers.<provider>.*`, `http.request_timeout`, and `http.verify_ssl`.
It rejects missing endpoint/model/credentials and unresolved key placeholders.
Explicit providers do not fail over silently. Optional `provider` and `model`
arguments override selection for a caller; `ollama_base_url` only overrides
Ollama, never the destination of remote API credentials.

`get_chat_models(settings)` lists installed Ollama models or the configured
remote/mock model; errors propagate so each UI can report them appropriately.
For auto-detected model discovery, use
`get_chat_settings(manager, resolve_auto=True)` first.

An application with a config cache can pass its **already resolved** mapping
directly to the factory, or use `ConfigManager(config=resolved_config)`. The
manager copies that snapshot and does not reread files or reapply layers.
The snapshot is not revalidated; schema validation belongs to initial config
loading. This also keeps provider detection and client construction on the
same configuration snapshot.

The returned `AIClient` retains `chat`, `chat_stream`, `achat`, and
`achat_stream`. Its default async methods use thread wrappers; they are not a
replacement for the true-async `AsyncOpenAIClient` or application-specific
`ProviderChain`/cancellation workflows.

Keep domain retrieval, prompt composition, conversation history, persistence
and framework-specific error handling in the application. `ki-knowledge` uses
this factory; existing `kicli-code-assist` client construction can migrate to
it incrementally without changing its session/workflow abstractions.

## Adapter contract

Implement `AIClient`:

- `chat(request: ChatRequest) -> ChatResponse`
- `chat_stream(request: ChatRequest) -> Iterator[StreamEvent]`

## Versioning

`0.1.0a1` initializes the core contract for parallel integration in both projects.
