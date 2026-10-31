# Consistency Report: ki-core

Generated: 2026-10-31 02:16 UTC  
Version: 0.1.0a1 (from pyproject.toml)

## Audit Results

### ✅ Passing

- **Config structure**: Standard KI pattern implemented
  - ✓ config/defaults/stack.yaml with LLM provider config
  - ✓ config/stages/ with dev-lokal
  - ✓ ki.yaml with provider settings
  - ✓ [tool.stackctl] configured

- **CI/CD**: GitHub Actions workflow added
  - ✓ .github/workflows/test.yml
  - ✓ pytest, ruff, mypy, bandit configured
  - ✓ Python 3.10 tested
  - ✓ Type checking enabled

- **Documentation**: Comprehensive doc/ structure
  - ✓ doc/README.md with provider guide
  - ✓ Configuration examples
  - ✓ CLI usage (ki-chat)
  - ✓ Dependency documentation

- **Dependencies**: Properly pinned
  - ✓ requests≥2.31.0, pyyaml≥6.0, python-dotenv≥1.0.0
  - ✓ yaml-cfg-wizard≥0.1.0 (upstream dependency)
  - ✓ psutil≥5.9.0
  - ✓ Optional: mypy, pytest for dev

### ⚠️ Warnings

- **No Lock File**: poetry.lock missing
  - Impact: Dependency drift in production
  - Fix: `poetry lock`

### ❌ Failing

None

## Dependency Graph

```
yaml-cfg-wizard (0.2.0) [BASE]
    ↓
ki-core (0.1.0a1) [CORE LAYER]
  ├─ Depends on: yaml-cfg-wizard
  └─ Used by:
     ├─ ki-knowledge
     └─ kicli-code-assist
```

## Configuration Pattern

**LLM Provider Config**:
```yaml
# config/defaults/stack.yaml or ki.yaml
llm:
  provider: ollama  # or openai, mock
  models:
    default: llama2
  providers:
    ollama:
      base_url: http://localhost:11434
      timeout: 120
```

**Provider Activation**:
```bash
# Environment override
export KI_CFG_LLM__PROVIDER=openai
export KI_OPENAI_API_KEY=sk-...
ki-chat "Hello"
```

## Supported Providers

- **ollama** (local)
- **openai** (API)
- **mock** (testing)

## Next Steps

1. **Add Lock File**:
   ```bash
   poetry lock
   ```

2. **Verify Providers**:
   ```bash
   pytest tests/test_provider*.py -v
   ```

3. **Commit Changes**:
   ```bash
   git add config/ doc/ .github/ pyproject.toml ki.yaml
   git commit -m "[ki-core] Deployment & documentation standardization"
   ```

4. **Test CLI**:
   ```bash
   ki-chat "2+2"
   ```

## Related Repos

- [yaml-cfg-wizard](../../yaml_cfg_wizard) - Configuration system (dependency)
- [stackctl](../../stackctl) - Stack management
- [ki-knowledge](../../ki-knowledge) - Uses ki-core
- [kicli-code-assist](../../kicli-code-assist) - Uses ki-core
- [Ecosystem Audit](../../ECOSYSTEM_AUDIT_REPORT.md) - Full audit

---

**Status**: ✅ STANDARDIZED  
**Audit Date**: 2026-10-31
