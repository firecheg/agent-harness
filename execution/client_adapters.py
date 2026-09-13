"""Generic MCP/hook registration for configured clients; rollback preserves
unrelated edits.

Every client this module touches comes from an explicit manifest (see
client_manifest.py); there is no built-in `.claude`/`.codex` special case.
JSON-configured clients (most editors, including the optional native Claude
profile) use a `keys` path into a JSON document. Clients whose configuration
is not JSON (the optional native Codex profile uses TOML) fall back to a
marker-delimited text fragment describing the same MCP server.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys


def _long_path(path):
    """Normalize Windows 8.3 components without following links.

    ``Path.resolve`` is intentionally not used here: this value is only for
    the lexical containment check in ``_safe_path``.  Physical containment is
    checked separately after resolving the target and its parent.
    """
    lexical = Path(os.path.abspath(path))
    if os.name != 'nt':
        return lexical
    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        get_long = kernel32.GetLongPathNameW
        get_long.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_long.restype = ctypes.c_uint32
    except (AttributeError, OSError):
        return lexical

    # GetLongPathNameW rejects a path with a missing final component, so ask
    # for the longest existing prefix and append the untouched suffix.
    missing = []
    existing = lexical
    while not os.path.lexists(existing) and existing != existing.parent:
        missing.append(existing.name)
        existing = existing.parent
    if not os.path.lexists(existing):
        return lexical
    size = 260
    while True:
        buffer = ctypes.create_unicode_buffer(size)
        length = get_long(str(existing), buffer, size)
        if not length:
            return lexical
        if length < size:
            return Path(buffer.value).joinpath(*reversed(missing))
        size = length + 1

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from client_manifest import ClientManifestError, load_clients, validate_clients

SERVER_NAME = 'agent_harness'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get(data, keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def put(data, keys, value):
    parents = []
    for key in keys[:-1]:
        parents.append((data, key))
        data = data.setdefault(key, {})
    if value is None:
        data.pop(keys[-1], None)
        for parent, key in reversed(parents):
            child = parent.get(key)
            if isinstance(child, dict) and not child:
                parent.pop(key, None)
            else:
                break
    else:
        data[keys[-1]] = value


def _resolve_clients(shared, clients):
    if clients is not None:
        return validate_clients(clients)
    manifest_path = Path(shared) / 'clients.json'
    return load_clients(str(manifest_path)) if manifest_path.exists() else load_clients()


def _safe_path(path, home, label):
    """Return an absolute path whose existing parents stay inside ``home``.

    Manifest paths are lexical relative paths, but a parent can still be a
    junction or symlink.  Resolve both the target and its parent before any
    caller creates a directory or writes a file.
    """
    physical_home = Path(home).resolve()
    home = _long_path(home)
    lexical = _long_path(path)
    if lexical == home or not lexical.is_relative_to(home):
        raise ValueError(f'{label} escapes home: {lexical}')
    try:
        resolved = lexical.resolve(strict=False)
        parent = lexical.parent.resolve(strict=False)
    except OSError as exc:
        raise ValueError(f'cannot resolve {label}: {lexical}: {exc}') from exc
    if not resolved.is_relative_to(physical_home) or not parent.is_relative_to(physical_home):
        raise ValueError(f'{label} escapes home: {lexical}')
    return lexical


def _validate_client_paths(home, clients):
    for name, entry in clients.items():
        for kind in ('mcp', 'hook'):
            declaration = entry.get(kind)
            if declaration:
                _safe_path(home / declaration['path'], home, f'client {name!r} {kind} path')


def _validate_state_paths(state, home, shared):
    _safe_path(shared / 'adapters.json', home, 'adapter state')
    for op in state.get('json', []) + state.get('fragments', []):
        _safe_path(op['path'], home, 'managed adapter path')


def _server(python, mam, environ=None):
    environ = os.environ if environ is None else environ
    env = {'AGENT_HARNESS_HOME': str(mam)}
    for key in ('AGENT_HARNESS_CONFIG', 'AGENT_HARNESS_MEMORY', 'AGENT_HARNESS_SHARED'):
        value = environ.get(key)
        if value:
            env[key] = value
    return {'command': str(python),
            'args': ['-X', 'utf8', str(Path(mam) / 'execution/context_server.py')],
            'env': env}


def _hook_command(python, mam):
    return '"' + str(python) + '" -X utf8 "' + str(Path(mam) / 'execution/context_budget.py') + '" hook'


def _markers(marker):
    return f'# BEGIN agent-harness managed: {marker}', f'# END agent-harness managed: {marker}'


def _fragment_block(entry_mcp, server):
    env_lines = ''.join(f'{key} = {json.dumps(value)}\n' for key, value in server['env'].items())
    body = entry_mcp['template'].format(name=SERVER_NAME, command_json=json.dumps(server['command']),
                                        args_json=json.dumps(server['args']), env_lines=env_lines)
    start, end = _markers(entry_mcp['marker'])
    return start + '\n' + body + ('' if body.endswith('\n') else '\n') + end + '\n'


def _fragment_present(path, marker):
    if not path.exists():
        return False
    start, _ = _markers(marker)
    return start in path.read_text(encoding='utf-8-sig')


def issues(shared, allow_partial=False, home=None):
    """Report managed settings that no longer match what was applied."""
    shared = Path(shared)
    preflight_home = Path(home).resolve() if home is not None else Path(os.path.abspath(shared)).parent
    state_path = shared / 'adapters.json'
    _safe_path(state_path, preflight_home, 'adapter state')
    state = load(state_path)
    problems = []
    if not state or state.get('status') == 'rolled_back':
        return problems
    home = Path(home or state.get('home') or Path(shared).parent).resolve()
    try:
        _validate_state_paths(state, home, Path(shared))
    except ValueError as exc:
        problems.append(str(exc))
        return problems
    partial = allow_partial and state.get('status') == 'applying'
    if state.get('status') != 'active' and not partial:
        problems.append('unfinished adapter transaction; run configure or rollback to recover')
    for op in state.get('json', []):
        current = get(load(Path(op['path'])), op['keys'])
        if current != op['new'] and not (partial and current == op['old']):
            problems.append('changed managed setting: ' + op['path'] + ' ' + '.'.join(op['keys']))
    for op in state.get('fragments', []):
        path = Path(op['path'])
        text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
        if op['block'] not in text:
            untouched = partial and op['block'] not in text and not _fragment_present(path, op['marker'])
            if not untouched:
                problems.append('changed managed config fragment: ' + op['path'])
    return problems


def configure(home, shared, mam, python, clients=None, environ=None):
    home, shared, mam = (Path(p).resolve() for p in (home, shared, mam))
    _safe_path(shared, home, 'adapter state directory')
    resolved = _resolve_clients(shared, clients)
    _validate_client_paths(home, resolved)
    state_path = shared / 'adapters.json'
    _safe_path(state_path, home, 'adapter state')
    previous = load(state_path)
    if previous.get('status') == 'active':
        _validate_state_paths(previous, home, shared)
        found = issues(shared, home=home)
        if found:
            raise ValueError('; '.join(found))
        return previous
    if previous.get('status') == 'applying':
        rollback(shared, home)
    server = _server(python, mam, environ)
    hook_command = _hook_command(python, mam)
    json_ops, fragment_ops = [], []
    for name, entry in resolved.items():
        mcp = entry.get('mcp')
        if mcp and mcp['format'] == 'json':
            path = home / mcp['path']
            if get(load(path), mcp['keys']) is not None:
                raise ValueError(f'pre-existing {SERVER_NAME} MCP for client {name!r} requires manual merge')
            json_ops.append({'client': name, 'kind': 'mcp', 'path': str(path),
                             'keys': list(mcp['keys']), 'new': server})
        elif mcp:
            path = home / mcp['path']
            if _fragment_present(path, mcp['marker']):
                raise ValueError(f'pre-existing agent-harness config fragment for client {name!r} requires manual merge')
            fragment_ops.append({'client': name, 'path': str(path), 'marker': mcp['marker'],
                                 'block': _fragment_block(mcp, server)})
        hook = entry.get('hook')
        if hook:
            path = home / hook['path']
            existing = get(load(path), hook['keys']) or []
            hook_value = {'matcher': hook['matcher'],
                          'hooks': [{'type': 'command', 'command': hook_command, 'timeout': 10}]}
            json_ops.append({'client': name, 'kind': 'hook', 'path': str(path),
                             'keys': list(hook['keys']), 'new': [*existing, hook_value]})
    for op in json_ops:
        op['old'] = get(load(Path(op['path'])), op['keys'])
    state = {'status': 'applying', 'home': str(home), 'shared': str(shared),
             'json': json_ops, 'fragments': fragment_ops}
    write(state_path, state)
    try:
        for op in json_ops:
            path = Path(op['path'])
            data = load(path)
            if get(data, op['keys']) != op['old']:
                raise ValueError('configuration changed during migration: ' + op['path'])
            put(data, op['keys'], op['new'])
            write(path, data)
        for op in fragment_ops:
            path = Path(op['path'])
            _safe_path(path, home, 'managed adapter path')
            path.parent.mkdir(parents=True, exist_ok=True)
            old_text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
            if op['block'] in old_text:
                continue
            path.write_text(old_text + ('' if not old_text or old_text.endswith('\n') else '\n')
                            + '\n' + op['block'], encoding='utf-8')
        state['status'] = 'active'
        write(state_path, state)
    except Exception:
        _validate_state_paths(state, home, shared)
        for op in json_ops:
            path = Path(op['path'])
            data = load(path)
            if get(data, op['keys']) == op['new']:
                put(data, op['keys'], op['old'])
                write(path, data)
        for op in fragment_ops:
            path = Path(op['path'])
            if path.exists():
                text = path.read_text(encoding='utf-8-sig')
                if op['block'] in text:
                    path.write_text(text.replace('\n' + op['block'], '', 1).replace(op['block'], '', 1),
                                    encoding='utf-8')
        state['status'] = 'rolled_back'
        write(state_path, state)
        raise
    return state


def rollback(shared, home=None):
    shared = Path(shared)
    preflight_home = Path(home).resolve() if home is not None else Path(os.path.abspath(shared)).parent
    _safe_path(shared, preflight_home, 'adapter state directory')
    state_path = shared / 'adapters.json'
    _safe_path(state_path, preflight_home, 'adapter state')
    state = load(state_path)
    if not state or state.get('status') == 'rolled_back':
        return
    home = Path(home or state.get('home') or shared.parent).resolve()
    _safe_path(shared, home, 'adapter state directory')
    _validate_state_paths(state, home, shared)
    found = issues(shared, allow_partial=True, home=home)
    if found:
        raise ValueError('; '.join(found))
    for op in state.get('json', []):
        path = Path(op['path'])
        data = load(path)
        if get(data, op['keys']) == op['new']:
            put(data, op['keys'], op['old'])
            write(path, data)
    for op in state.get('fragments', []):
        path = Path(op['path'])
        if path.exists():
            text = path.read_text(encoding='utf-8-sig')
            if op['block'] in text:
                replaced = text.replace('\n' + op['block'], '', 1)
                if replaced == text:
                    replaced = text.replace(op['block'], '', 1)
                path.write_text(replaced, encoding='utf-8')
    state['status'] = 'rolled_back'
    write(shared / 'adapters.json', state)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['configure', 'upgrade', 'doctor', 'rollback'])
    p.add_argument('--home', type=Path, default=Path.home())
    p.add_argument('--mam', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--clients', type=Path, help='client manifest JSON; default is empty (no clients)')
    a = p.parse_args()
    shared = a.home / '.agent-harness'
    clients = validate_clients(json.loads(a.clients.read_text(encoding='utf-8'))) if a.clients else None
    error = None
    try:
        if a.command == 'upgrade':
            rollback(shared, a.home)
            configure(a.home, shared, a.mam, sys.executable, clients)
        elif a.command == 'configure':
            configure(a.home, shared, a.mam, sys.executable, clients)
        elif a.command == 'rollback':
            rollback(shared, a.home)
    except (ValueError, ClientManifestError) as exc:
        error = str(exc)
    result = {'problems': [error]} if error else {'problems': issues(shared, home=a.home)}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(bool(result['problems']))
