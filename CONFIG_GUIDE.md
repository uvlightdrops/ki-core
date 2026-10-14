# KI configuration guide

The canonical YAML operating guide is maintained in yaml-cfg-wizard:
[YAML_CONFIG_SYSADMIN.md](../yaml_cfg_wizard/doc/YAML_CONFIG_SYSADMIN.md).
It covers ki-core's real precedence, file discovery, selectors, credential
paths and validation boundaries, plus each consuming application's differences.

Generic architecture and future ideas:
[YAML_CONFIG_CONCEPTS.md](../yaml_cfg_wizard/doc/YAML_CONFIG_CONCEPTS.md).
Superseded excerpts from this guide:
[YAML_CONFIG_ARCHIVE.md](../yaml_cfg_wizard/doc/YAML_CONFIG_ARCHIVE.md).
These relative links assume sibling checkouts; otherwise open the named files
in the yaml-cfg-wizard repository. ki-core is a framework, so it links the guide
instead of maintaining a separate app copy.

The implementation contract is `src/ki_core/config.py`; base schema:
`src/ki_core/schema/config.schema.yaml`. From low to high:
schema defaults -> defaults directory -> ki.yaml -> selected profile ->
selected stage -> runtime -> KI_CFG_* -> creds.yaml.
Credentials use the same consumed nested paths as the main configuration,
not an automatically unwrapped `creds.llm` namespace.
`load_config()` returns `ConfigDict`; applications own their typed accessors.
Base validation plus merged-schema default filling is not full final
application-schema validation. See the canonical guide before editing.
