import os
from pathlib import Path
import re
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "mam.py", "pyproject.toml", "README.md", ".github/workflows/ci.yml",
    "execution/providers.py", "execution/cold_start.py",
    "execution/reasoning_router.py", "execution/worker_cli.py",
    "execution/context_server.py", "execution/context_budget.py",
    "execution/read_gate.py", "execution/index_workers.py",
    "graphs/build.json", "presets/codex.json", "skills/multi-agent/SKILL.md",
    "examples/rules/routing.md", "tools/check_publication.py",
    "tools/smoke_installed.py", "tests/test_mam.py",
)
FORBIDDEN = (
    "execution/client_adapters.py", "execution/client_manifest.py",
    "execution/shared_harness.py", "execution/specify_project.py",
    "skills/shared-harness/SKILL.md", "examples/clients-example.json",
    "examples/clients-claude-codex.json", "examples/shared-rules.md",
    "docs/client-integration.md", "PROVENANCE.md", "tools/export_mod.py",
    "tools/mod/README.md", "tests/test_client_adapters.py",
    "tests/test_shared_harness.py", "tests/test_specify_project.py",
    "tests/test_export_mod.py",
)
FORBIDDEN_TEXT = (
    "client-integration.md", "PROVENANCE.md", "shared-rules.md",
    "clients-claude-codex.json", "clients-example.json", "skills/shared-harness",
    "test_client_adapters", "test_shared_harness", "test_specify_project",
    "client_adapters", "client_manifest", "shared_harness", "specify_project",
)
FORBIDDEN_TEXT_PATTERNS = (re.compile(r"clients-[^\s)`]+\.json", re.I),
                           re.compile(r"\bluna\b|\bastra\b", re.I))


class ExportTests(unittest.TestCase):
    def test_export_is_self_contained_and_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "mod"
            subprocess.run([sys.executable, "tools/export_mod.py", str(destination)],
                           cwd=ROOT, check=True)
            paths = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
            for path in REQUIRED:
                self.assertIn(path, paths)
                self.assertTrue((destination / path).is_file(), path)
            for path in FORBIDDEN:
                self.assertNotIn(path, paths)
            for path in destination.rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8")
                    self.assertFalse(any(term in text for term in FORBIDDEN_TEXT), path)
                    self.assertFalse(any(pattern.search(text) for pattern in FORBIDDEN_TEXT_PATTERNS), path)
                    if path.suffix.lower() == ".md":
                        for target in re.findall(r"(?<!!)\[[^]]*\]\(([^)]+)\)", text):
                            if target.startswith(("#", "/", "\\")) or "://" in target:
                                continue
                            link = target.split("#", 1)[0]
                            if link:
                                resolved = (path.parent / link).resolve()
                                self.assertTrue(resolved.is_relative_to(destination.resolve()), (path, target))
                                self.assertTrue(resolved.is_file(), (path, target))
            env = os.environ.copy()
            for key in list(env):
                if key.startswith("MAM_") or key.startswith("AGENT_HARNESS_"):
                    env.pop(key)
            test_tmp = destination / ".tmp"
            test_tmp.mkdir()
            env["TEMP"] = str(test_tmp)
            env["TMP"] = str(test_tmp)
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".",
                       "-p", "test_*.py"]
            subprocess.run(command, cwd=destination, env=env, check=True)
            subprocess.run([sys.executable, "tools/check_publication.py", "."],
                           cwd=destination, env=env, check=True)


if __name__ == "__main__":
    unittest.main()
