# Secrets Management Strategy

**Status:** Documented and implemented (Phase 2+)  
**Scope:** All ki ecosystem apps (ki-knowledge, kicli-code-assist, ki-chat, stackctl)

## Core Principle

Secrets are **host-local responsibility**. The config system doesn't classify what's secret—the host does.

## The 9-Layer Model with Secrets

Config resolution order (highest to lowest priority):

```
1. creds.yaml          ← SECRETS WIN HERE (override everything)
2. KI_CFG_* env vars
3. config/runtime/*.yaml
4. Active stage
5. Active profile
6. ki.yaml
7. config/defaults/*.yaml
8. Schema defaults
```

**Critical rule:** `creds.yaml` wins even over `KI_CFG_*` environment variables.

## Where Secrets Live

Store secrets **at the path where they're consumed**, e.g.:

```yaml
# In ki.yaml (plaintext or placeholder):
llm:
  providers:
    openai:
      api_key: "${OPENAI_API_KEY}"    # Placeholder
    ollama:
      base_url: "http://localhost:11434"
    ki:
      api_key: "${KI_API_KEY}"         # Placeholder

# In creds.yaml (NEVER committed):
llm:
  providers:
    openai:
      api_key: "sk-proj-..."           # Real key (deep-merged)
    ki:
      api_key: "ki-..."                # Real key (deep-merged)
```

**No wrapper paths** like `creds:` or `secrets:`. The secret goes directly where it's used.

## Deployment Workflow

### Local Development

```bash
# 1. Create ki.yaml with placeholders or defaults
echo "llm:" > ki.yaml
echo "  providers:" >> ki.yaml
echo "    openai:" >> ki.yaml
echo "      api_key: \"\${OPENAI_API_KEY}\"" >> ki.yaml

# 2. Create creds.yaml with real secrets (locally only)
echo "llm:" > creds.yaml
echo "  providers:" >> creds.yaml
echo "    openai:" >> creds.yaml
echo "      api_key: \"sk-proj-...\"" >> creds.yaml

# 3. Add creds.yaml to .gitignore (essential!)
echo "creds.yaml" >> .gitignore
```

### Environment Variables

For CI/CD or containers, use `KI_CFG_*` env vars:

```bash
export KI_CFG_LLM__PROVIDERS__OPENAI__API_KEY="sk-proj-..."
export KI_CFG_LLM__PROVIDERS__KI__API_KEY="ki-..."

# kicli-assist will merge these on top of ki.yaml
kicli-assist tui
```

**But remember:** If `creds.yaml` exists, it wins even over `KI_CFG_*`.

### Hosting / Production

Target hosts with creds.yaml:

```bash
# On production host
cd /opt/ki-apps/kicli-code-assist
cat > creds.yaml << EOF
llm:
  providers:
    openai:
      api_key: "sk-proj-..."
    ki:
      api_key: "ki-..."
EOF
chmod 600 creds.yaml  # Read by owner only
```

Then run:

```bash
kicli-assist config resolve  # Will merge creds.yaml on top
kicli-assist tui             # Reads resolved config
```

## Secret Filtering in Logs

The `SensitiveDataFilter` (in `ki_core.security.filters`) automatically redacts:

- API keys: `"sk-proj-..."` → `"sk-proj-[REDACTED]"`
- URLs with credentials: `"https://user:pass@host"` → sanitized
- Known secret patterns: Custom patterns per app

**How it works:**

1. All loggers in kicli-code-assist pass through `SensitiveDataFilter`
2. Before any log message hits disk, secrets are masked
3. Filter respects per-module level overrides from `ki.yaml` logging section

**Example:**

```yaml
# ki.yaml
logging:
  level: INFO
  per_module:
    kicli.llm: DEBUG    # LLM logs at DEBUG level even when global is INFO
  format: "%(asctime)s [%(levelname)s] %(message)s"
```

Then:

```python
logger.debug(f"OpenAI key: {openai_key}")
# Log output: "OpenAI key: sk-proj-[REDACTED]" (even at DEBUG level, never leaks)
```

## Validation & Discovery

ConfigManager validates secrets against schema **only for structure**, never for content:

```yaml
# schema: this location must be a string
llm.providers.openai.api_key: type: string

# ki.yaml: placeholder or env var is OK
llm:
  providers:
    openai:
      api_key: "${OPENAI_API_KEY}"

# creds.yaml: real key is deep-merged in
llm:
  providers:
    openai:
      api_key: "sk-proj-..."
```

No attempt to check whether a key is "real" or "fake"—validation only checks types and schema shape.

## Checklist: Deploying a New App

1. **Schema section** (schema/*.schema.yaml): Define where secrets go
   ```yaml
   llm:
     providers:
       openai:
         api_key: { type: string }
   ```

2. **Defaults** (ki.yaml or config/defaults/): Use placeholders
   ```yaml
   llm:
     providers:
       openai:
         api_key: "${OPENAI_API_KEY}"
   ```

3. **Local dev** (creds.yaml): Create locally, add to .gitignore
   ```yaml
   # .gitignore
   creds.yaml
   ```

4. **Deployment script**: Ensure creds.yaml is deployed to target (not from repo!)
   ```bash
   # e.g., in Ansible, systemd service, or Helm chart:
   - name: Write secrets
     copy:
       content: |
         llm:
           providers:
             openai:
               api_key: "{{ openai_api_key }}"
       dest: /opt/ki/creds.yaml
       mode: "0600"
   ```

5. **Testing**: Verify config merges correctly
   ```bash
   kicli-assist config resolve    # Should show merged config (secrets masked in output)
   ```

## FAQ

**Q: Why not encrypt creds.yaml?**  
A: Host security (file permissions, SELinux, disk encryption) is simpler and more reliable than format-specific encryption. If creds.yaml is at risk, the host itself is compromised.

**Q: Can I store secrets in ki.yaml?**  
A: Technically yes, but **don't**—it gets committed to git. Use placeholders in ki.yaml; real secrets go in creds.yaml or env vars.

**Q: What if I forget to .gitignore creds.yaml?**  
A: You've leaked secrets. Add creds.yaml to .gitignore immediately. Then (carefully) rotate all exposed keys. For recovery:
  ```bash
  git rm --cached creds.yaml
  git commit -m "Remove creds.yaml from history"
  git push
  ```
  But **key rotation is still necessary**—git history can be recovered.

**Q: Does ConfigManager validate creds.yaml?**  
A: Yes, against schema structure (types, required fields). No, against key validity—a fake key passes validation.

**Q: Can I override creds.yaml with KI_CFG_*?**  
A: No. creds.yaml always wins (layer 1 priority). This ensures secrets can't be accidentally overridden by casual env var mistakes.

## See Also

- `YAML_CONFIG_SYSADMIN.md`: Full 9-layer reference
- `YAML_CONFIG_CONCEPTS.md`: Architectural reasoning
- `ki_core/security/filters.py`: Secret filtering implementation
- `.gitignore` patterns: Repos should ignore `creds.yaml`, `*.env`, personal config files
