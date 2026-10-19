# Config Validation & Error Handling Guide

**Status:** Implemented (Phase 2+)  
**Audience:** App users, developers, ops engineers  

## Quick Diagnosis

When you see a config error, the source is usually one of these:

### Error: "No module named 'ki_core'"

**Cause:** ki-core not installed or not in PYTHONPATH  
**Fix:**
```bash
pip install -e ../ki-core          # From app repo (if checking out locally)
# OR
pip install ki-core                 # From PyPI (when released)
```

---

### Error: "config file not found" / "ki.yaml not discovered"

**Cause:** ki.yaml is missing or in wrong location  
**Fix:**
```bash
# Check search paths (in order):
# 1. Explicit --config /path/to/ki.yaml
# 2. ./ki.yaml (current directory)
# 3. ~/.config/ki/ki.yaml (home directory)

# Create one with defaults:
kicli-assist config skeleton -o ki.yaml

# Or explicitly specify:
kicli-assist --config /etc/ki/ki.yaml tui
```

---

### Error: "schema validation failed" / "Additional properties not allowed"

**Cause:** ki.yaml has fields not defined in schema, or wrong types  
**Fix:**

1. **Check the schema:**
   ```bash
   cat ki-core/src/ki_core/schema/config.schema.yaml
   ```

2. **Remove unexpected fields:**
   ```yaml
   # WRONG: "foo" not in schema
   foo: bar
   
   # RIGHT: Use only schema-defined paths
   llm:
     providers:
       openai:
         api_key: "sk-..."
   ```

3. **Validate before committing:**
   ```bash
   yaml-cfg config verify ki.yaml schema/app.schema.yaml
   ```

---

### Error: "Profile 'local' not found" / "Stage 'dev' not found"

**Cause:** Active profile/stage doesn't exist  
**Fix:**
```bash
# Check what exists:
ls -la config/profiles/
ls -la config/stages/

# Create one:
cat > config/profiles/local.yaml << EOF
llm:
  providers:
    openai:
      base_url: "http://localhost:8000"
EOF

# Set as active:
echo local > config/profiles/.active_profile
# OR with env var:
export KI_PROFILE=local
```

---

### Error: "creds.yaml has invalid schema"

**Cause:** creds.yaml has fields that don't match base schema structure  
**Fix:**
```bash
# creds.yaml must have the SAME structure as ki.yaml
# It doesn't add new fields—it only overrides existing ones

# WRONG:
---
# creds.yaml
new_secret_format: "secret"    # ← Not in schema

# RIGHT:
---
# creds.yaml
llm:
  providers:
    openai:
      api_key: "sk-..."         # ← This path exists in schema
```

---

### Error: "Circular reference" or "Recursive merge detected"

**Cause:** Config references itself (rare, usually in YAML anchors)  
**Fix:**
```bash
# Remove YAML anchors/references:
# WRONG:
defaults: &default_cfg
  timeout: 30
http:
  <<: *default_cfg    # ← Merging anchors can cause issues

# RIGHT:
http:
  request_timeout: 30
```

---

## Validation in AppConfig

When you load config in Python:

```python
from ki_core import ConfigManager

mgr = ConfigManager()
config = mgr.load()  # Returns ConfigDict (always valid by schema)
```

**ConfigManager guarantees:**
- ✅ All schema-defined defaults are present
- ✅ Environment variables (KI_CFG_*) are properly merged
- ✅ creds.yaml secrets are deep-merged
- ✅ Profile/stage overrides are applied
- ✅ Final dict validates against schema

**What it doesn't guarantee:**
- ❌ Your app-specific logic (e.g., "base_url must end in /")
- ❌ Runtime constraints (e.g., "port must be > 1024")
- ❌ Inter-field dependencies (e.g., "if auth is oauth, secret must exist")

For those, add **custom validation**:

```python
def validate_llm_config(config: ConfigDict) -> None:
    """Custom validation for LLM-specific constraints."""
    provider = config.get_path("llm.provider", "auto")
    
    if provider == "openai":
        key = config.get_path("llm.providers.openai.api_key", "")
        if not key or key.startswith("${"):
            raise ValueError("OpenAI selected but api_key is placeholder")
    
    elif provider == "ollama":
        url = config.get_path("llm.providers.ollama.base_url", "")
        if not url.startswith("http"):
            raise ValueError(f"Ollama base_url must be HTTP: {url}")

# Usage
config = mgr.load()
validate_llm_config(config)  # Raises early with clear message
```

---

## Debugging Tips

### 1. Dry-Run Config Resolution

See what config resolves to **without running the app**:

```bash
# Show full resolved config
kicli-assist config resolve

# Show just a specific path
kicli-assist config show llm.providers.openai

# Show what profile/stage is active
kicli-assist config show --active-layers
```

### 2. Check Each Layer Separately

```bash
# Just defaults
yaml-cfg config resolve --defaults-dir config/defaults

# Defaults + ki.yaml
yaml-cfg config resolve --defaults-dir config/defaults --defaults ki.yaml

# Add profile
yaml-cfg config resolve \
  --defaults-dir config/defaults \
  --defaults ki.yaml \
  --profile config/profiles/local.yaml

# Add stage
yaml-cfg config resolve \
  --defaults-dir config/defaults \
  --defaults ki.yaml \
  --profile config/profiles/local.yaml \
  --stage config/stages/dev.yaml
```

### 3. Check Secrets Separately

```bash
# Resolve WITHOUT creds.yaml (see placeholders)
kicli-assist config resolve

# Verify creds.yaml structure (doesn't show secret values!)
yaml-cfg config verify creds.yaml schema/app.schema.yaml

# After merging, secrets are in resolved config (shown masked in logs)
```

### 4. Environment Variable Override

Test KI_CFG_* without changing ki.yaml:

```bash
export KI_CFG_LLM__PROVIDERS__OPENAI__API_KEY="test-key"
kicli-assist config show llm.providers.openai.api_key

# Check precedence (env var should override ki.yaml)
```

### 5. Enable Debug Logging

```bash
# Log layer-by-layer merging
export KI_CFG_LOGGING__LEVEL="DEBUG"
kicli-assist tui  # Now shows config resolution steps

# Or in ki.yaml:
logging:
  level: DEBUG
  per_module:
    ki_core.config: DEBUG  # Verbose config module
```

---

## Common Mistakes

| Mistake | Issue | Fix |
|---------|-------|-----|
| `foo: bar` in ki.yaml | Field not in schema | Remove or define in schema |
| Placeholder key in ki.yaml, nothing in creds.yaml | Secret is literally `"${KEY}"` string | Add real key to creds.yaml |
| creds.yaml has new sections | Schema mismatch | creds.yaml can only override, not extend |
| Different structure in profile | Profile can't add new top-level keys | Profile must match base schema |
| `config/runtime/` missing | Runtime layer skipped silently | Create directory if using runtime overrides |
| `.active_profile` file doesn't exist | Profile layer skipped (no error) | Create marker file with profile name |
| KI_PROFILE env var typo | Wrong profile loaded, no error | Check spelling: `export KI_PROFILE=local` |

---

## Testing Your Config

### Before Deployment

```bash
#!/bin/bash
set -e

APP="kicli-code-assist"
CONFIG_PATH="/path/to/deployment/ki.yaml"
CREDS_PATH="/path/to/deployment/creds.yaml"

# 1. Verify structure
yaml-cfg config verify "$CONFIG_PATH" schema/app.schema.yaml
yaml-cfg config verify "$CREDS_PATH" schema/app.schema.yaml

# 2. Resolve all layers (without showing secrets)
yaml-cfg config resolve \
  --defaults-dir config/defaults \
  --defaults "$CONFIG_PATH" \
  --stage "config/stages/prod.yaml"

# 3. Check critical paths exist
config_path="${CONFIG_PATH}" python3 << 'EOF'
from ki_core import ConfigManager
mgr = ConfigManager(config_path=os.getenv("config_path"))
config = mgr.load()
assert config.get_path("llm.providers.openai.api_key"), "OpenAI key missing"
assert config.get_path("system.workspace_root"), "Workspace root missing"
print("✓ All critical config paths present")
EOF

# 4. Try provider detection
python3 << 'EOF'
from ki_core import ConfigManager
mgr = ConfigManager()
provider = mgr.get_llm_provider()
print(f"✓ Provider detected: {provider}")
EOF
```

---

## Schema Extension (For App Developers)

If your app needs config beyond ki-core's base schema:

1. **Create** `schema/app.schema.yaml` in your repo
2. **Define** your app's section:
   ```yaml
   # schema/kicli.schema.yaml
   $schema: "http://json-schema.org/draft-7/schema#"
   type: object
   properties:
     apps:
       type: object
       properties:
         kicli:
           type: object
           properties:
             workspace_root: { type: string }
             context:
               type: object
               properties:
                 max_files: { type: integer }
   ```
3. **Reference** both schemas in config commands:
   ```bash
   yaml-cfg config verify ki.yaml \
     schema/app.schema.yaml \
     schema/kicli.schema.yaml
   ```

ConfigManager auto-discovers `schema/*.schema.yaml`, so no extra setup needed.

---

## See Also

- `SECRETS_MANAGEMENT.md`: How to store secrets safely
- `YAML_CONFIG_SYSADMIN.md`: The 9-layer reference
- `ki-core/src/ki_core/schema/config.schema.yaml`: The authoritative schema
