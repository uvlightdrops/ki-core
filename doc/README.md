# ki-core Documentation

## Overview
`ki-core` is the shared AI client abstraction layer for the KI ecosystem. It provides:
- Unified LLM provider access (OpenAI, Ollama, Mock)
- Layered configuration management via yaml-cfg-wizard
- CLI tool for AI chat (`ki-chat`)
- Environment variable secrets support
- Provider-specific error handling and utilities

**Status**: Early alpha (0.1.0a1)  
**Python**: ≥3.10  

## Quick Start

```bash
pip install ki-core
```

```python
from ki_core import AIClient, get_chat_factory

# Create AI client
client = AIClient()

# Or use factory for streaming
factory = get_chat_factory()
response = factory.chat(messages=[...])
```

```bash
# CLI chat with Ollama
ki-chat "What is 2+2?"
```

## Configuration

ki-core uses the **yaml-cfg-wizard** config pattern:

```yaml
# config/defaults/stack.yaml
llm:
  provider: ollama
  models:
    default: llama2
  providers:
    ollama:
      base_url: http://localhost:11434
      timeout: 120
```

Override via environment:
```bash
export KI_CFG_LLM__PROVIDER=openai
export KI_OPENAI_API_KEY=sk-...
ki-chat "Hello"
```

## Providers

- **openai**: OpenAI API (requires API key)
- **ollama**: Local Ollama instance (recommended for dev)
- **mock**: Testing provider (always returns test responses)

## Architecture

```
ki_core/
├── client/           # AIClient implementations
├── providers/        # OpenAI, Ollama, Mock adapters
├── config/           # Configuration management
├── schema/           # YAML schema definitions
├── cli/              # CLI commands (ki-chat)
└── errors/           # Provider-specific exceptions
```

## Dependencies

- requests ≥2.31.0 (HTTP client)
- pyyaml ≥6.0 (YAML parsing)
- python-dotenv ≥1.0.0 (Environment secrets)
- yaml-cfg-wizard ≥0.1.0 (Config system)
- psutil ≥5.9.0 (Process utilities)

## See Also

- [yaml-cfg-wizard](../yaml_cfg_wizard) - Config system (dependency)
- [ki-knowledge](../ki-knowledge) - Uses ki-core for LLM access
- [kicli-code-assist](../kicli-code-assist) - Uses ki-core for code generation
- [stackctl](../stackctl) - Stack management (consumes config)

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/
mypy src/ki_core
```

## Testing Providers

```bash
# Test with Mock provider (default in tests)
pytest tests/

# Test with local Ollama
pip install -e ".[ollama]"
ollama serve &
KI_CFG_LLM__PROVIDER=ollama pytest tests/
```

## License

MIT
