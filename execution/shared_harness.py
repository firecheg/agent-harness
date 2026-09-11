"""Shared skill catalog and reversible client resource linking.

Skills live once, under a canonical shared root, and are exposed to each
configured client by a directory link (a Windows junction or a POSIX
symlink) — never copied per client. Which clients participate, and where
each one expects its skills and instructions, comes from an explicit client
manifest (see client_manifest.py); there is no built-in client list, and no
actual `.claude`/`.codex` directory is touched unless the caller's manifest
names it.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

_HERE = Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from client_manifest import load_clients, validate_clients


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def inside(path, root):
    # Check the lexical path before touching a link, and the physical root too.
    path, root = Path(os.path.abspath(path)), Path(root).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError(f'path outside allowed root: {path}')
    return path


def tree_files(root):
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            child = Path(directory) / name
            is_junction = getattr(child, 'is_junction', lambda: False)()
            if child.is_symlink() or is_junction:
                raise ValueError(f'nested directory link requires explicit handling: {child}')
        for name in files:
            child = Path(directory) / name
            if child.is_symlink():
                raise ValueError(f'nested file link requires explicit handling: {child}')
            result[child.relative_to(root).as_posix()] = digest(child)
    return result


def _resolve_clients(shared, clients):
    if clients is not None:
        return validate_clients(clients)
    manifest_path = Path(shared) / 'clients.json'
    return load_clients(str(manifest_path)) if manifest_path.exists() else load_clients()


def plan(home, shared, mam, clients=None):
    home, shared, mam = Path(home).resolve(), Path(shared).resolve(), Path(mam).resolve()
    inside(shared, home)
    resolved = _resolve_clients(shared, clients)
    harness_skills = (mam / 'skills').resolve()
    skills, conflicts = {}, []
    for name, entry in resolved.items():
        if 'skills_dir' not in entry:
            continue
        root = home / entry['skills_dir']
        if not root.exists():
            continue
        if not root.resolve().is_relative_to(home):
            raise ValueError(f'skills directory escapes home: {root}')
        for child in sorted(root.iterdir()):
            if child.name.startswith('.') or not (child / 'SKILL.md').is_file():
                continue
            resolved_child = child.resolve()
            # A skill already living under the harness's own bundled catalog
            # is canonical as-is; anything else outside `home` needs an
            # explicit `register()` call rather than being folded in here.
            approved_external = resolved_child.is_relative_to(harness_skills)
            if not resolved_child.is_relative_to(home) and not approved_external:
                raise ValueError(f'external skill link requires explicit registration: {child}')
            skill = skills.setdefault(child.name, {'source': str(resolved_child), 'originals': [],
                                                    'canonical': resolved_child if approved_external else None})
            skill['originals'].append(str(child))
    for name, entry in skills.items():
        canonical = entry.pop('canonical')
        entry['target'] = str(canonical if canonical is not None else shared / 'skills' / name)
        sources = list(dict.fromkeys(str(Path(p).resolve()) for p in entry['originals']))
        entry['sources'] = sources
        hashes = {}
        for source in sources:
            for relative, sha in tree_files(Path(source)).items():
                if relative in hashes and hashes[relative] != sha:
                    conflicts.append({'skill': name, 'file': relative, 'winner': entry['source'], 'alternate': source})
                hashes.setdefault(relative, sha)
        entry['hashes'] = hashes
    return {'home': str(home), 'shared': str(shared), 'mam': str(mam), 'clients': list(resolved),
            'skills': skills, 'conflicts': conflicts}


def junction(path, target):
    if os.name == 'nt':
        env = {**os.environ, 'AGENT_HARNESS_LINK_PATH': str(path), 'AGENT_HARNESS_LINK_TARGET': str(target)}
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                        "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path $env:AGENT_HARNESS_LINK_PATH -Target $env:AGENT_HARNESS_LINK_TARGET | Out-Null"],
                       env=env, check=True, capture_output=True)
    else:
        os.symlink(target, path, target_is_directory=True)


def check_operation(op):
    path = Path(op['path'])
    if op['kind'] in ('directory', 'hardlink'):
        if not path.exists() or not os.path.samefile(path, op['target']):
            raise ValueError(f'changed link: {path}')
    elif not path.is_file() or digest(path) != op['sha256']:
        raise ValueError(f'changed configuration: {path}')


def apply(home, shared, mam, rules, clients=None):
    home, shared, mam = Path(home).resolve(), Path(shared).resolve(), Path(mam).resolve()
    inside(shared, home)
    state_path = shared / 'state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state['status'] == 'active':
            for operation in state['operations']:
                check_operation(operation)
            return state
        if state['status'] != 'rolled_back':
            raise ValueError('unfinished transaction; inspect state.json before continuing')
    inventory = plan(home, shared, mam, clients)
    if inventory['conflicts']:
        details = ', '.join(
            f"{item['skill']}/{item['file']} ({item['winner']} vs {item['alternate']})"
            for item in inventory['conflicts'])
        raise ValueError(f'skill conflicts prevent apply: {details}')
    transaction = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    backup = shared / 'backups' / transaction
    backup.mkdir(parents=True)
    save(backup / 'plan.json', inventory)
    core = shared / 'rules/AGENTS.md'
    core.parent.mkdir(parents=True, exist_ok=True)
    core.write_text(rules, encoding='utf-8')
    # Build and verify the canonical shared catalog first; client paths are
    # not touched until every canonical skill is in place and consistent.
    for name, entry in inventory['skills'].items():
        target = Path(entry['target'])
        if target.is_relative_to(mam / 'skills'):
            if not (target / 'SKILL.md').exists():
                raise ValueError(f'harness-bundled skill target missing: {target}')
            continue
        if target.exists():
            if tree_files(target) != entry['hashes']:
                raise ValueError(f'pre-existing canonical skill differs: {target}')
            continue
        for source in entry['sources']:
            for relative in tree_files(Path(source)):
                dest = target / relative
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(Path(source) / relative, dest)
        if tree_files(target) != entry['hashes']:
            raise ValueError(f'copy verification failed: {target}')
    resolved = _resolve_clients(shared, clients)
    state = {'transaction': transaction, 'home': str(home), 'shared': str(shared),
             'status': 'applying', 'operations': [], 'skills': inventory['skills'],
             'clients': list(resolved)}
    save(state_path, state)

    def replace(path, kind, target=None, text=None):
        path = inside(path, home)
        # A parent junction must not be able to steer this operation outside home.
        inside(path.parent.resolve(), home)
        path.parent.mkdir(parents=True, exist_ok=True)
        old = backup / 'originals' / path.relative_to(home)
        exists = os.path.lexists(path)
        op = {'path': str(path), 'kind': kind, 'backup': str(old) if exists else None}
        if target is not None:
            op['target'] = str(Path(target).resolve())
        # Recording intent lets a stopped process still recover cleanly.
        op['phase'] = 'planned'
        state['operations'].append(op)
        save(state_path, state)
        if exists:
            old.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, old)
        op['phase'] = 'backed_up'
        save(state_path, state)
        if kind == 'directory':
            junction(path, target)
        elif kind == 'hardlink':
            os.link(target, path)
        else:
            path.write_text(text, encoding='utf-8')
            op['sha256'] = digest(path)
        op['phase'] = 'installed'
        save(state_path, state)

    try:
        for name, entry in inventory['skills'].items():
            for client_name, client_entry in resolved.items():
                if 'skills_dir' not in client_entry:
                    continue
                replace(home / client_entry['skills_dir'] / name, 'directory', entry['target'])
        for client_name, client_entry in resolved.items():
            if 'instructions_file' in client_entry:
                replace(home / client_entry['instructions_file'], 'hardlink', core)
            if 'include_file' in client_entry:
                replace(home / client_entry['include_file'], 'file',
                       text=client_entry['include_template'].format(path=core.as_posix()))
        state['status'] = 'active'
        save(state_path, state)
    except Exception:
        # Only this call's own operations; originals were saved before linking.
        for op in reversed(state['operations']):
            path = Path(op['path'])
            if op['phase'] == 'installed':
                if op['kind'] == 'directory':
                    os.rmdir(path) if os.name == 'nt' else path.unlink()
                else:
                    path.unlink()
            if op['backup'] and Path(op['backup']).exists() and not os.path.lexists(path):
                os.replace(op['backup'], path)
        state['status'] = 'rolled_back'
        save(state_path, state)
        raise
    return state


def rollback(home, shared):
    home, shared = Path(home).resolve(), Path(shared).resolve()
    inside(shared, home)
    state_path = shared / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    if state['status'] == 'rolled_back':
        return state
    if state['status'] != 'active' or Path(state['home']) != home:
        raise ValueError('transaction is not active for this profile')
    # Verify everything BEFORE the first change: a user's edits stop the rollback.
    for op in state['operations']:
        inside(op['path'], home)
        if op['backup']:
            inside(op['backup'], shared)
            if not os.path.lexists(op['backup']):
                raise ValueError(f'missing backup: {op["backup"]}')
        check_operation(op)
    if (shared / 'adapters.json').exists():
        import client_adapters
        if client_adapters.issues(shared, allow_partial=True):
            raise ValueError('; '.join(client_adapters.issues(shared, allow_partial=True)))
        client_adapters.rollback(shared, home)
    for op in reversed(state['operations']):
        path = Path(op['path'])
        if op['kind'] == 'directory':
            os.rmdir(path) if os.name == 'nt' else path.unlink()
        else:
            path.unlink()
        if op['backup']:
            os.replace(op['backup'], path)
    state['status'] = 'rolled_back'
    save(state_path, state)
    return state


def doctor(home, shared):
    state = json.loads((Path(shared) / 'state.json').read_text(encoding='utf-8'))
    problems = []
    if state['status'] != 'active':
        problems.append('transaction is not active')
    for op in state['operations']:
        try:
            check_operation(op)
        except (ValueError, OSError) as exc:
            problems.append(str(exc))
    if (Path(shared) / 'adapters.json').exists():
        import client_adapters
        problems.extend(client_adapters.issues(shared))
    return {'status': state['status'], 'skills': len(state['skills']),
            'transaction': state['transaction'], 'problems': problems}


def register(home, shared, mam, source, clients=None):
    home, shared, mam, source = (Path(p).resolve() for p in (home, shared, mam, source))
    inside(shared, home)
    if not source.is_relative_to(shared / 'skills') and not source.is_relative_to(mam / 'skills'):
        raise ValueError('skill source must be in the shared catalog or the harness skills')
    if not (source / 'SKILL.md').is_file():
        raise ValueError('SKILL.md missing')
    state_path = shared / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    if state['status'] != 'active':
        raise ValueError('migration must be active')
    resolved = _resolve_clients(shared, clients)
    name = source.name
    paths = [home / entry['skills_dir'] / name for entry in resolved.values() if 'skills_dir' in entry]
    canonical = shared / 'skills' / name
    if source != canonical:
        paths.insert(0, canonical)
    for path in paths:
        inside(path, home)
        inside(path.parent.resolve(), home)
        if os.path.lexists(path) and not os.path.samefile(path, source):
            raise ValueError(f'existing skill differs: {path}')
    created = []
    try:
        for path in paths:
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            junction(path, source)
            created.append(path)
            state['operations'].append({'path': str(path), 'kind': 'directory', 'backup': None,
                                        'target': str(source), 'phase': 'installed'})
        state['skills'][name] = {'source': str(source), 'target': str(source), 'originals': []}
        save(state_path, state)
    except Exception:
        for path in reversed(created):
            os.rmdir(path) if os.name == 'nt' else path.unlink()
        raise
    return {'registered': name, 'source': str(source)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'apply', 'doctor', 'rollback', 'add'])
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--shared', type=Path)
    parser.add_argument('--mam', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--rules', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--clients', type=Path,
                        help='client manifest JSON; default is empty (no clients) unless '
                             'AGENT_HARNESS_CLIENTS or <shared>/clients.json is set')
    args = parser.parse_args()
    shared = args.shared or args.home / '.agent-harness'
    clients = validate_clients(json.loads(args.clients.read_text(encoding='utf-8'))) if args.clients else None
    if args.command == 'add':
        if not args.source:
            parser.error('--source required')
        result = register(args.home, shared, args.mam, args.source, clients)
    elif args.command == 'plan':
        result = plan(args.home, shared, args.mam, clients)
    elif args.command == 'apply':
        if not args.rules:
            parser.error('--rules required')
        result = apply(args.home, shared, args.mam, args.rules.read_text(encoding='utf-8'), clients)
        result = {'status': result['status'], 'transaction': result['transaction'], 'skills': len(result['skills'])}
    elif args.command == 'rollback':
        result = rollback(args.home, shared)
        result = {'status': result['status'], 'transaction': result['transaction']}
    else:
        result = doctor(args.home, shared)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('problems'):
        sys.exit(1)


if __name__ == '__main__':
    main()
