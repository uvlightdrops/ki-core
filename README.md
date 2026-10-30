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

### Schema-driven runtime settings (Django, Flask, CLI)

`ki_core.runtime_settings` has no Django dependency. Hosts can reuse the same
service from any framework:

```python
from pathlib import Path
from ki_core.runtime_settings import RuntimeSettings, ConflictError, ValidationError

settings = RuntimeSettings(
    Path("/srv/my-project"),
    restart_paths=("apps.my_app.worker",),
    excluded_paths=("apps.my_app.database_owned",),
)
snapshot = settings.snapshot()
snapshot = settings.save(snapshot["revision"], {"http.request_timeout": 45})
snapshot = settings.save(snapshot["revision"], {}, remove=("http.request_timeout",))
```

The JSON-compatible snapshot contains a revision and individually discovered
schema rows, never a raw resolved configuration dump. Rows describe types,
enums, effective/runtime values, editability/reasons, higher-layer shadowing,
configured-secret status, and restart requirements. Schemas are merged from
ki-core and the project's `schema/*.schema.yaml`. Typed arrays and closed objects,
including maps with explicitly typed `additionalProperties`, are editable only
when their entire schema is safe. Nullable/union values must satisfy their schema.
Unknown schema-less subtrees are inventoried read-only without exposing values.
Open objects, unsupported schema constructs, secret-containing containers,
secret fields and application exclusions are not editable. Add a precise schema
to register additional settings; never accept arbitrary request paths.

Writes target only `<project>/config/runtime/runtime.yaml`, reject symlinked
targets, serialize under an advisory lock, detect stale revisions
(`ConflictError`), validate both submitted fields and the merged effective
configuration (`ValidationError`), and atomically replace the file with mode
`0600`. Removal replaces the runtime layer during resolution, preserving lower
defaults/profile/stage values and higher `KI_CFG_*` / `creds.yaml` precedence.
`resolve_runtime_candidate(root, candidate, config_path=...)` shares that
resolution pipeline with legacy adapters; its **internal** result includes
credentials and must never be exposed to a client. Like `load_config`, this
resolver performs base-schema validation; the editor additionally validates the
merged application schema at save time.

Secret values, unsafe URLs and untyped containers are not returned. Values sourced from
credentials are configured-only and read-only, even for an otherwise editable
field. Environment shadowing is shown explicitly. Default restart markers cover
deployment/bootstrap/server/database/storage/logging paths; applications extend
these markers for their startup-cached settings. LLM/HTTP settings are not
blanket-marked for restart. “Dynamic” means the host must reload configuration
when building its next operation/client; this service does not mutate already
running workers or replace their cached clients. Authentication and CSRF belong
in the framework adapter (see `widgetkit_django.runtime_settings`).

Write-only credential editing uses a **separate transaction/revision**:

```python
credentials = settings.secret_snapshot()  # only paths/configured/overridden flags
credentials = settings.save_secret(
    credentials["revision"], "llm.providers.openai.api_key", new_key,
)
credentials = settings.remove_secret(credentials["revision"], "llm.providers.openai.api_key")
```

These methods return the same configured-only `secret_snapshot` shape, never
values. Only registered scalar string secret fields are supported; application
exclusions/read-only schemas still apply. Blank/whitespace input leaves a field
unchanged (it is not deletion). Removal deletes only the credentials override:
environment/runtime/default layers may still provide a value. Placeholder values
are never echoed. `ConflictError` applies to the credentials revision independently
of runtime edits; `ValidationError` rejects invalid paths/values or effective
merged configuration. There is deliberately no mixed-layer atomic save.

The active project-local `creds.yaml` or `config/creds.yaml` is preserved; without
one, writes create project-root `creds.yaml`. Active credentials outside the
project, symlinked targets/parents, or unsafe roots are rejected without migration
or silently shadowing the active credentials. Writes reuse the same advisory
locking/atomic replacement and force mode `0600`. Ordinary `Editor` users still
cannot register secret paths. Already-created clients do not magically refresh;
hosts must reload on their next operation (or restart startup-cached clients).

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
