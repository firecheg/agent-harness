"""Spec Kit 1.0.4 wrapper: stage the official scaffold, then add only missing files.

Spec Kit itself is an optional external CLI, resolved from PATH (or an
explicit path); this module never downloads it and never touches the
network. Integration names ("claude", "codex", ...) are Spec Kit's own
vendor-integration identifiers, not this project's provider configuration;
override them with `--integration` (repeatable) or AGENT_HARNESS_SPECIFY_INTEGRATIONS
when your client uses a different one.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

VERSION = '1.0.4'
DEFAULT_INTEGRATIONS = ('claude', 'codex')


def fingerprint(path):
    data = path.read_bytes()
    if path.name.endswith('.manifest.json') or path.name == 'workflow-registry.json':
        def stable(value):
            if isinstance(value, dict):
                return {k: stable(v) for k, v in value.items() if k not in {'installed_at', 'updated_at'}}
            if isinstance(value, list):
                return [stable(v) for v in value]
            return value
        data = json.dumps(stable(json.loads(data)), sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def manifest(root):
    return {p.relative_to(root).as_posix(): fingerprint(p)
            for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}


def _integrations(integrations=None):
    if integrations is not None:
        return list(integrations)
    env = os.environ.get('AGENT_HARNESS_SPECIFY_INTEGRATIONS')
    return [name.strip() for name in env.split(',') if name.strip()] if env else list(DEFAULT_INTEGRATIONS)


def initialize(project, apply=False, integrations=None, specify_path=None):
    project = Path(project)
    if not project.is_absolute() or not project.is_dir():
        raise ValueError('an absolute path to an existing project is required')
    project = project.resolve()
    exe = specify_path or shutil.which('specify')
    if not exe:
        raise ValueError('specify is not installed; see the client-integration docs for the optional Spec Kit setup')
    integrations = _integrations(integrations)
    if not integrations:
        raise ValueError('at least one Spec Kit integration is required')
    version = subprocess.run([exe, 'version'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', check=True)
    if VERSION not in version.stdout:
        raise ValueError('expected specify version ' + VERSION)
    # The official scaffold is assembled once, in a scratch directory; only
    # files this project does not already have are ever copied out of it.
    with tempfile.TemporaryDirectory(prefix='agent-harness-specify-') as tmp:
        stage = Path(tmp) / 'project'
        first, rest = integrations[0], integrations[1:]
        subprocess.run([exe, 'init', str(stage), '--integration', first, '--script', 'ps',
                        '--non-interactive', '--ignore-agent-tools'],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for name in rest:
            subprocess.run([exe, 'integration', 'install', name, '--script', 'ps'], cwd=stage,
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        desired = manifest(stage)
        conflicts = []
        new = []
        for relative, sha in desired.items():
            destination = project / relative
            if not destination.resolve().is_relative_to(project):
                raise ValueError('link takes the target path outside the project: ' + relative)
            if destination.exists():
                if not destination.is_file() or fingerprint(destination) != sha:
                    conflicts.append(relative)
            else:
                new.append(relative)
        result = {'project': str(project), 'version': VERSION, 'integrations': integrations,
                  'new': new, 'conflicts': conflicts, 'applied': False}
        if not apply:
            return result
        if conflicts:
            raise ValueError('existing files differ; nothing changed: ' + ', '.join(conflicts))
        created = []
        try:
            for relative in new:
                target = project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation guards against edits made after the preview.
                with target.open('xb') as output:
                    created.append(target)
                    output.write((stage / relative).read_bytes())
        except Exception:
            for target in reversed(created):
                target.unlink()
            raise
        result['applied'] = True
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='default is preview only')
    parser.add_argument('--integration', action='append', dest='integrations',
                        help='repeatable; default is claude,codex or AGENT_HARNESS_SPECIFY_INTEGRATIONS')
    a = parser.parse_args()
    try:
        print(json.dumps(initialize(a.project, a.apply, a.integrations), ensure_ascii=False, indent=2))
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, str(exc) + '\n')
