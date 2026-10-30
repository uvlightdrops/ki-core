"""Schema-discovered runtime overrides, independent of any web framework."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from jsonschema import Draft7Validator
from yaml_cfg_wizard.core import env_to_dict, load_yaml_file
from yaml_cfg_wizard.editor import (
    ConflictError, Editor, EditorError, Field, ValidationError, _MISSING, _get,
)
from yaml_cfg_wizard.schema_utils import merge_schemas

from . import config

DEFAULT_RESTART_PATHS = (
    "stack", "deployment", "django", "database", "storage", "logging",
    "server", "paths", "bootstrap", "profiles", "stages", "system.config_path",
)
_SECRET = re.compile(
    r"secret|password|passwd|token|credential|api[_-]?key|private[_-]?key|"
    r"(^|[._])dsn($|[._])|authorization|cookie", re.I,
)
_PATH = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")
_HIDDEN = "[verborgen: Zugangsdaten/unsicherer Wert]"


def _under(path: str, prefixes: Sequence[str]) -> bool:
    return any(path == p or path.startswith(p + ".") for p in prefixes)


def _sensitive(path: str, schema: Mapping[str, Any]) -> bool:
    return bool(_SECRET.search(path) or schema.get("writeOnly") or
                schema.get("format") == "password" or schema.get("x-secret"))


def _types(schema: Mapping[str, Any]) -> list[str]:
    value = schema.get("type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    alternatives = schema.get("anyOf", schema.get("oneOf", []))
    if alternatives:
        return list(dict.fromkeys(t for s in alternatives for t in _types(s)))
    if "properties" in schema or "additionalProperties" in schema:
        return ["object"]
    if "enum" in schema:
        return list(dict.fromkeys(
            "null" if v is None else "boolean" if isinstance(v, bool) else
            "integer" if isinstance(v, int) else "number" if isinstance(v, float) else
            "string" if isinstance(v, str) else "object" for v in schema["enum"]
        ))
    return []


def _safe_schema(schema: Any, path: str = "") -> bool:
    if not isinstance(schema, dict) or _sensitive(path, schema) or schema.get("readOnly"):
        return False
    if "$ref" in schema or "allOf" in schema:
        return False
    if "anyOf" in schema or "oneOf" in schema:
        return all(_safe_schema(s, path) for s in schema.get("anyOf", schema.get("oneOf")))
    types = _types(schema)
    if not types:
        return False
    if "array" in types and not _safe_schema(schema.get("items"), path):
        return False
    if "object" in types:
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if not all(_safe_schema(s, f"{path}.{p}") for p, s in props.items()):
            return False
        if additional is not False and not _safe_schema(additional, path):
            return False
        if not props and additional is False:
            return True
    return True


def _unsafe(value: Any, secrets: Sequence[str] = (), depth: int = 0) -> bool:
    if depth > 30:
        return True
    if isinstance(value, dict):
        return any(not isinstance(k, str) or _SECRET.search(k) or
                   _unsafe(v, secrets, depth + 1) for k, v in value.items())
    if isinstance(value, list):
        return any(_unsafe(v, secrets, depth + 1) for v in value)
    if isinstance(value, str):
        if any(s and s in value for s in secrets):
            return True
        if re.search(r"(?i)(bearer\s+\S+|(?:password|token|secret|api_key)\s*[=:])", value):
            return True
        urls = re.findall(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+", value)
        if urls:
            try:
                for url in urls:
                    parts = urlsplit(url)
                    if parts.username or parts.password or parts.query or parts.fragment:
                        return True
            except ValueError:
                return True
        return False
    if isinstance(value, float):
        return not math.isfinite(value)
    return value is not None and not isinstance(value, (int, bool))


def resolve_runtime_candidate(
    project_root: Path, candidate: Mapping[str, Any], *, config_path: Path | None = None,
) -> dict[str, Any]:
    """Resolve a replacement runtime layer through the normal ki-core pipeline.

    Internal resolved values include credentials: never send this result to a client.
    """
    try:
        if not isinstance(candidate, Mapping):
            raise TypeError
        return config._resolve_config(
            config_path, runtime_candidate=candidate, project_root=Path(project_root).absolute(),
        )
    except Exception:
        raise ValidationError("Konfiguration konnte nicht schema-gültig aufgelöst werden.") from None


class _RuntimeEditor(Editor):
    def _validate_changes(self, changes):
        for value in changes.values():
            if _unsafe(value):
                raise ValidationError("Nur sichere, zugangsdatenfreie Werte sind erlaubt.")

    def _file_mode(self, target, raw):
        return 0o600

    def _validate_effective_values(self, effective):
        # Higher layers may legitimately contain credential-bearing URLs.
        # Submitted values are checked above; snapshots redact every layer.
        pass


class _CredentialsEditor(Editor):
    """Dedicated write-only transaction; never registers general Editor fields."""

    def __init__(self, target, paths, resolve, schema):
        super().__init__({"credentials": target}, (), resolve, schema)
        self._paths = set(paths)

    def _file_mode(self, target, raw):
        return 0o600

    def _validate_changes(self, changes):
        if any(not isinstance(value, str) or not value.strip() for value in changes.values()):
            raise ValidationError("Zugangsdaten müssen nichtleere Zeichenketten sein.")


class RuntimeSettings:
    """Edit only discovered, safe schema fields in a fixed project runtime file."""

    def __init__(
        self, project_root: Path, *, restart_paths: tuple[str, ...] = (),
        excluded_paths: tuple[str, ...] = (),
    ):
        self.project_root = Path(project_root).absolute()
        self.target = self.project_root / "config/runtime/runtime.yaml"
        self.restart_paths = (*DEFAULT_RESTART_PATHS, *restart_paths)
        self.excluded_paths = excluded_paths
        self._check_target()
        try:
            self.schema = merge_schemas(*config.get_merged_schemas(self.project_root))
            Draft7Validator.check_schema(self.schema)
        except Exception:
            raise EditorError("Konfigurationsschema konnte nicht geladen werden.") from None
        self.fields: dict[str, dict[str, Any]] = {}
        self._discover(self.schema)
        editable = [Field(p, p) for p, s in self.fields.items() if not self._reason(p, s)]
        self.editor = _RuntimeEditor(
            {"runtime": self.target}, editable,
            lambda _, candidate: resolve_runtime_candidate(self.project_root, candidate), self.schema,
        )

    def _check_target(self):
        for path in (self.target, *self.target.parents):
            if path.is_symlink():
                raise EditorError("Symlink-Konfigurationspfade sind nicht erlaubt.")
        if not self.target.resolve().is_relative_to(self.project_root.resolve()):
            raise EditorError("Konfigurationsziel liegt außerhalb des Projekts.")

    def _discover(self, schema, prefix=""):
        for name, child in schema.get("properties", {}).items():
            path = f"{prefix}.{name}" if prefix else name
            if not isinstance(child, dict):
                child = {}
            if child.get("properties") and not _sensitive(path, child):
                self._discover(child, path)
            else:
                self.fields[path] = child

    def _reason(self, path, schema):
        if _under(path, self.excluded_paths) or any(
            p.startswith(path + ".") for p in self.excluded_paths
        ):
            return "Anderer Eigentümer (z. B. Datenbank); im zuständigen Verwaltungsbereich ändern."
        if _sensitive(path, schema):
            return "Zugangsdaten ausschließlich in creds.yaml verwalten."
        if schema.get("readOnly"):
            return "Schema ist schreibgeschützt."
        if not _PATH.fullmatch(path) or not _safe_schema(schema, path):
            return "Offenes/mehrdeutiges Schema; kein sicherer Laufzeit-Editor verfügbar."
        return ""

    def _credentials(self):
        path = config._find_creds_yaml_path(self.project_root / "ki.yaml")
        return load_yaml_file(path) if path else {}

    def _snapshot(self):
        self._check_target()
        try:
            _, raw, data = self.editor._read("runtime")
            effective = self.editor._effective("runtime", data)
            creds = self._credentials()
            env = env_to_dict("KI_CFG_")
            secret_values = []

            def collect(node):
                if isinstance(node, dict):
                    for v in node.values():
                        collect(v)
                elif isinstance(node, list):
                    for v in node:
                        collect(v)
                elif isinstance(node, str) and node:
                    secret_values.append(node)

            collect(creds)
            for path, schema in self.fields.items():
                if _sensitive(path, schema):
                    for source in (effective, data):
                        value = _get(source, path)
                        if value is not _MISSING:
                            collect(value)
            rows = []
            for path, schema in self.fields.items():
                override, value = _get(data, path), _get(effective, path)
                reason = self._reason(path, schema)
                credential = _get(creds, path) is not _MISSING
                secret = _sensitive(path, schema) or credential
                safe_schema = _safe_schema(schema, path)
                if credential:
                    reason = "Durch creds.yaml verwaltet; Zugangsdaten dort ändern."
                shadowed_by = "creds.yaml" if credential else "KI_CFG_*" if _get(env, path) is not _MISSING else None

                def display(v):
                    if v is _MISSING:
                        return None
                    return _HIDDEN if secret or not safe_schema or _unsafe(v, secret_values) else v

                def metadata(v):
                    return "" if _unsafe(v, secret_values) else v

                types = _types(schema)
                row = {
                    "path": path, "label": metadata(schema.get("title", path)),
                    "description": metadata(schema.get("description", "")),
                    "type": types[0] if len(types) == 1 else types, "types": types,
                    "enum": [v for v in schema.get("enum", []) if safe_schema and not secret and not _unsafe(v, secret_values)],
                    "effective": display(value), "override": display(override),
                    "overridden": override is not _MISSING, "configured": value is not _MISSING and value not in (None, ""),
                    "editable": not reason, "reason": reason, "secret": secret,
                    "restart_required": _under(path, self.restart_paths) or bool(re.search(r"(^|[._])dsn($|[._])", path, re.I)),
                    "shadowed": bool(shadowed_by), "shadowed_by": shadowed_by,
                }
                rows.append(row)

            def unknown(node, schema, prefix=""):
                if not isinstance(node, dict):
                    return
                properties = schema.get("properties", {})
                for name, value in node.items():
                    if not isinstance(name, str):
                        continue
                    path = f"{prefix}.{name}" if prefix else name
                    if name in properties:
                        child = properties[name]
                        if isinstance(child, dict) and child.get("properties"):
                            unknown(value, child, path)
                    else:
                        safe_path = path if _PATH.fullmatch(path) and not _unsafe(path, secret_values) else (
                            f"{prefix}.[nicht registrierte Schlüssel]" if prefix else "[nicht registrierte Schlüssel]"
                        )
                        rows.append({
                            "path": safe_path, "label": safe_path, "description": "",
                            "type": "unknown", "types": [], "enum": [], "effective": None,
                            "override": None, "overridden": False, "configured": True,
                            "editable": False, "reason": "Kein registriertes Schema; Werte werden nicht angezeigt.",
                            "secret": True, "restart_required": _under(path, self.restart_paths),
                            "shadowed": False, "shadowed_by": None,
                        })

            unknown(effective, self.schema)
            return {"revision": self.editor._revision(raw), "rows": rows,
                    "target": "config/runtime/runtime.yaml",
                    "warnings": ["Schema-lose Einstellungen sind nur als schreibgeschütztes Inventar sichtbar."]
                    if any(r["type"] == "unknown" for r in rows) else []}
        except EditorError:
            raise
        except Exception:
            raise EditorError("Konfiguration konnte nicht sicher gelesen werden.") from None

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot()

    def save(
        self, revision: str, changes: Mapping[str, Any], remove: Sequence[str] = (),
    ) -> dict[str, Any]:
        self._check_target()
        try:
            if not isinstance(changes, Mapping) or isinstance(remove, (str, bytes)):
                raise ValidationError("Ungültige Änderungen.")
            editable = {r["path"] for r in self.snapshot()["rows"] if r["editable"]}
            if (set(changes) | set(remove)) - editable:
                raise ValidationError("Feld ist nicht bearbeitbar.")
            # The editor's transaction owns locking, conflicts, schema validation
            # and atomic replacement. Its scalar-only snapshot is not exposed.
            self.editor.save("runtime", revision, changes, remove)
            return self.snapshot()
        except EditorError:
            raise
        except Exception:
            raise ValidationError("Konfiguration konnte nicht gespeichert werden.") from None

    def _secret_fields(self):
        return {
            path: schema for path, schema in self.fields.items()
            if _sensitive(path, schema) and set(_types(schema)) - {"null"} == {"string"}
            and _PATH.fullmatch(path) and not schema.get("readOnly")
        }

    def _credential_target(self):
        active = config._find_creds_yaml_path(self.project_root / "ki.yaml")
        target = Path(active).absolute() if active else self.project_root / "creds.yaml"
        allowed = {self.project_root / "creds.yaml", self.project_root / "config/creds.yaml"}
        if target not in allowed:
            raise EditorError("Aktive Zugangsdaten liegen außerhalb des Projekts; dort verwalten.")
        for path in (target, *target.parents):
            if path.is_symlink():
                raise EditorError("Symlink-Zugangsdatenpfade sind nicht erlaubt.")
        if not target.resolve().is_relative_to(self.project_root.resolve()):
            raise EditorError("Zugangsdatenziel liegt außerhalb des Projekts.")
        return target

    def _credentials_editor(self):
        self._check_target()
        target = self._credential_target()

        def resolve(_, candidate):
            try:
                # Replace credentials, do not merge on old creds: deleting an
                # override must expose runtime/env/default values again.
                return config._resolve_config(
                    project_root=self.project_root, creds_candidate=candidate,
                )
            except Exception:
                raise ValidationError("Zugangsdaten-Konfiguration ist ungültig.") from None

        return _CredentialsEditor(target, self._secret_fields(), resolve, self.schema)

    def secret_snapshot(self) -> dict[str, Any]:
        """Configured-only credential inventory with its own optimistic revision."""
        try:
            editor = self._credentials_editor()
            _, raw, data = editor._read("credentials")
            effective = editor._effective("credentials", data)
            rows = []
            for path, schema in self._secret_fields().items():
                value = _get(effective, path)
                overridden = _get(data, path) is not _MISSING
                reason = (
                    "Anderer Eigentümer; im zuständigen Verwaltungsbereich ändern."
                    if _under(path, self.excluded_paths) else ""
                )
                rows.append({
                    "path": path, "label": path,
                    "configured": value is not _MISSING and value not in (None, ""),
                    "overridden": overridden, "editable": not reason, "reason": reason,
                    "restart_required": _under(path, self.restart_paths) or bool(
                        re.search(r"(^|[._])dsn($|[._])", path, re.I)
                    ),
                })
            return {"revision": editor._revision(raw), "rows": rows, "editable": True,
                    "reason": "", "target": str(editor.files["credentials"].relative_to(self.project_root))}
        except EditorError:
            raise
        except Exception:
            raise EditorError("Zugangsdaten konnten nicht sicher gelesen werden.") from None

    def _save_secret(self, revision, path, value=None, *, remove=False):
        try:
            editor = self._credentials_editor()
            if path not in self._secret_fields() or _under(path, self.excluded_paths):
                raise ValidationError("Zugangsdatenfeld ist nicht bearbeitbar.")
            if not isinstance(revision, str):
                raise ValidationError("Ungültige Zugangsdatenrevision.")
            if not remove and isinstance(value, str) and not value.strip():
                # Blank password forms are intentionally no-ops, never deletions.
                if editor._revision(editor._read("credentials")[1]) != revision:
                    raise ConflictError("Zugangsdaten wurden inzwischen geändert. Neu laden.")
                return self.secret_snapshot()
            editor.save(
                "credentials", revision, {} if remove else {path: value},
                (path,) if remove else (),
            )
            return self.secret_snapshot()
        except EditorError:
            raise
        except Exception:
            raise ValidationError("Zugangsdaten konnten nicht gespeichert werden.") from None

    def save_secret(self, revision: str, path: str, value: str) -> dict[str, Any]:
        """Write one registered scalar secret, returning only configured status."""
        return self._save_secret(revision, path, value)

    def remove_secret(self, revision: str, path: str) -> dict[str, Any]:
        """Delete a credentials override; lower layers may still provide a secret."""
        return self._save_secret(revision, path, remove=True)


__all__ = ["RuntimeSettings", "EditorError", "ConflictError", "ValidationError",
           "resolve_runtime_candidate"]
