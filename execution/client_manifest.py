"""Generic client manifest: which files a client expects skills, instructions,
an MCP server registration or a read-gate hook in, and in what shape.

There is no built-in client list. A manifest is an explicit JSON mapping of
client name -> declaration; joining a new client (an editor, a different
agent CLI, ...) is adding an entry here, never editing this module. Optional
native Claude/Codex profiles ship as example manifests under examples/ and
must be opted into explicitly (AGENT_HARNESS_CLIENTS or --clients).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re


_NAME = re.compile(r"[a-z][a-z0-9-]*")
_MCP_FORMATS = {"json", "config_fragment"}
_HOOK_FORMATS = {"json"}


class ClientManifestError(ValueError):
    pass


def _string(value, label):
    if not isinstance(value, str) or not value:
        raise ClientManifestError(f"{label} must be a non-empty string")
    return value


def _relative_path(value, label):
    text = _string(value, label)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ClientManifestError(f"{label} must be a relative path inside the client's home")
    return text


def _string_list(value, label):
    if not isinstance(value, list) or not value or not all(
            isinstance(item, str) and item for item in value):
        raise ClientManifestError(f"{label} must be a non-empty list of non-empty strings")
    return list(value)


def _validate_mcp(raw, label):
    if not isinstance(raw, dict):
        raise ClientManifestError(f"{label} must be an object")
    fmt = raw.get("format")
    if fmt not in _MCP_FORMATS:
        raise ClientManifestError(f"{label}.format must be one of {sorted(_MCP_FORMATS)}")
    path = _relative_path(raw.get("path"), f"{label}.path")
    if fmt == "json":
        extra = set(raw) - {"format", "path", "keys"}
        if extra:
            raise ClientManifestError(f"{label}: unknown fields: {', '.join(sorted(extra))}")
        return {"format": fmt, "path": path, "keys": _string_list(raw.get("keys"), f"{label}.keys")}
    extra = set(raw) - {"format", "path", "marker", "template"}
    if extra:
        raise ClientManifestError(f"{label}: unknown fields: {', '.join(sorted(extra))}")
    marker = _string(raw.get("marker"), f"{label}.marker")
    template = _string(raw.get("template"), f"{label}.template")
    for token in ("{name}", "{command_json}", "{args_json}", "{env_lines}"):
        if token not in template:
            raise ClientManifestError(f"{label}.template must reference {token}")
    return {"format": fmt, "path": path, "marker": marker, "template": template}


def _validate_hook(raw, label):
    if not isinstance(raw, dict):
        raise ClientManifestError(f"{label} must be an object")
    fmt = raw.get("format", "json")
    if fmt not in _HOOK_FORMATS:
        raise ClientManifestError(f"{label}.format must be one of {sorted(_HOOK_FORMATS)}")
    extra = set(raw) - {"format", "path", "keys", "matcher"}
    if extra:
        raise ClientManifestError(f"{label}: unknown fields: {', '.join(sorted(extra))}")
    return {"format": fmt, "path": _relative_path(raw.get("path"), f"{label}.path"),
            "keys": _string_list(raw.get("keys"), f"{label}.keys"),
            "matcher": _string(raw.get("matcher"), f"{label}.matcher")}


def validate_clients(data):
    """Validate and normalize a client manifest; never touches the filesystem."""
    if not isinstance(data, dict):
        raise ClientManifestError("client manifest must be an object")
    result = {}
    for name, raw in data.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ClientManifestError(f"client name {name!r} must be a lowercase slug")
        if not isinstance(raw, dict):
            raise ClientManifestError(f"clients.{name} must be an object")
        allowed = {"skills_dir", "instructions_file", "include_file", "include_template", "mcp", "hook"}
        extra = set(raw) - allowed
        if extra:
            raise ClientManifestError(f"clients.{name}: unknown fields: {', '.join(sorted(extra))}")
        entry = {}
        for key in ("skills_dir", "instructions_file", "include_file"):
            if key in raw:
                entry[key] = _relative_path(raw[key], f"clients.{name}.{key}")
        if "include_file" in entry:
            entry["include_template"] = _string(raw.get("include_template"),
                                                 f"clients.{name}.include_template")
        elif "include_template" in raw:
            raise ClientManifestError(f"clients.{name}.include_template requires include_file")
        if "mcp" in raw:
            entry["mcp"] = _validate_mcp(raw["mcp"], f"clients.{name}.mcp")
        if "hook" in raw:
            entry["hook"] = _validate_hook(raw["hook"], f"clients.{name}.hook")
        result[name] = entry
    return result


def load_clients(path=None):
    """Load an explicit manifest, an env-selected one, or default to empty.

    Default clients are empty: nothing is registered for any actual client
    (`.claude`, `.codex`, or anything else) unless a manifest names it.
    """
    selected = path or os.environ.get("AGENT_HARNESS_CLIENTS")
    if not selected:
        return {}
    config_path = Path(selected).expanduser().resolve()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClientManifestError(f"cannot load client manifest {config_path}: {exc}") from exc
    return validate_clients(data)
