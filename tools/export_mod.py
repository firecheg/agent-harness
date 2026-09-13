"""Export the tracked multi-agent subset into an empty destination."""
from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path

INCLUDES = (
    "mam.py", "LICENSE", ".gitignore", "AGENTS.md", ".github/workflows/*",
    "execution/*.py", "demo/*", "graphs/*", "presets/*", "memory/SCHEMA.md",
    "skills/__init__.py", "skills/multi-agent/**", "examples/__init__.py",
    "examples/default-config.json", "examples/third-party-config.json",
    "examples/third-party-demo-config.json", "docs/*", "tools/check_publication.py",
    "tools/smoke_installed.py", "tests/*.py", "examples/rules/*",
)
EXCLUDES = {
    "PROVENANCE.md", "pyproject.toml", "README.md", "docs/client-integration.md",
    "execution/client_adapters.py", "execution/client_manifest.py",
    "execution/shared_harness.py", "execution/specify_project.py",
    "examples/clients-claude-codex.json", "examples/clients-example.json",
    "examples/shared-rules.md", "skills/shared-harness/**",
    "tests/test_client_adapters.py", "tests/test_shared_harness.py",
    "tests/test_specify_project.py",
    "tests/test_export_mod.py", "tools/export_mod.py", "tools/mod/**",
}
OVERLAYS = {
    "pyproject.toml": "pyproject.toml",
    "README.md": "README.md",
    ".github/workflows/ci.yml": "ci.yml",
}


def matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def tracked(root: Path) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True,
                            capture_output=True).stdout.decode().split("\0")
    return [path for path in result if path]


def export(destination: Path) -> int:
    root = Path(__file__).resolve().parents[1]
    destination = destination.resolve()
    tracked_files = tracked(root)
    files = [path for path in tracked_files if matches(path, INCLUDES) and not matches(path, EXCLUDES)]
    for pattern in INCLUDES:
        if not any(matches(path, (pattern,)) and not matches(path, EXCLUDES) for path in tracked_files):
            raise ValueError(f"include pattern matched nothing: {pattern}")
    overlay_sources = [f"tools/mod/{source}" for source in OVERLAYS.values()]
    missing = [path for path in overlay_sources if path not in tracked_files]
    if missing:
        raise ValueError("export inputs are not staged; stage or commit first: " + ", ".join(missing))
    export_inputs = files + overlay_sources
    unstaged = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--", *export_inputs],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    if unstaged:
        raise ValueError(
            "exported paths have unstaged changes; stage or commit first: "
            + ", ".join(unstaged)
        )
    if destination.exists():
        if not destination.is_dir() or any(p.name != ".git" for p in destination.iterdir()):
            raise ValueError("destination must be empty or contain only a .git directory")
        if (destination / ".git").exists() and not (destination / ".git").is_dir():
            raise ValueError("destination .git must be a directory")
    else:
        destination.mkdir(parents=True)

    for rel in files:
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = subprocess.run(["git", "-C", str(root), "show", f":{rel}"], check=True,
                             capture_output=True).stdout
        target.write_bytes(raw)
    for target_name, source_name in OVERLAYS.items():
        target = destination / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = subprocess.run(["git", "-C", str(root), "show", f":tools/mod/{source_name}"], check=True,
                             capture_output=True).stdout
        target.write_bytes(raw)
    print(json.dumps({"file_count": len(set(files) | set(OVERLAYS)), "dest": str(destination)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(export(Path(sys.argv[1])))
    except (IndexError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
