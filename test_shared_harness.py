import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'shared_harness', Path(__file__).parent / 'execution/shared_harness.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _is_junction(path):
    return getattr(path, 'is_junction', lambda: False)()


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / 'home'
        self.shared = self.home / '.agent-harness'
        self.mam = Path(self.tmp.name) / 'mam'
        self.mam.mkdir()
        self.clients = {
            'alpha': {
                'skills_dir': '.alpha/skills',
                'instructions_file': '.alpha/AGENTS.md',
            },
            'beta': {
                'skills_dir': '.beta/skills',
                'instructions_file': '.beta/AGENTS.md',
                'include_file': '.beta/INCLUDE.md',
                'include_template': '@{path}\n',
            },
        }
        for host in ('alpha', 'beta'):
            skill = self.home / f'.{host}/skills/demo'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('shared', encoding='utf-8')
        (self.home / '.beta/skills/demo/extra.txt').write_text('preserve', encoding='utf-8')
        (self.home / '.alpha/AGENTS.md').write_text('original alpha', encoding='utf-8')
        (self.home / '.beta/AGENTS.md').write_text('original beta', encoding='utf-8')

    def tearDown(self):
        for host in ('alpha', 'beta'):
            p = self.home / f'.{host}/skills/demo'
            target = self.shared / 'skills/demo'
            linked = _is_junction(p)
            if not linked and p.exists() and target.exists():
                try:
                    linked = os.path.samefile(p, target)
                except OSError:
                    linked = False
            if linked:
                os.rmdir(p) if os.name == 'nt' else p.unlink()
        self.tmp.cleanup()

    def test_plan_is_read_only_for_explicit_generic_clients(self):
        plan = module.plan(self.home, self.shared, self.mam, self.clients)
        self.assertFalse(self.shared.exists())
        self.assertEqual(plan['skills']['demo']['source'],
                         str((self.home / '.alpha/skills/demo').resolve()))
        self.assertEqual(plan['conflicts'], [])
        self.assertEqual(plan['clients'], ['alpha', 'beta'])

    def test_apply_idempotent_common_identity_and_rollback(self):
        result = module.apply(self.home, self.shared, self.mam, 'common rules', self.clients)
        a = self.home / '.alpha/skills/demo/SKILL.md'
        b = self.home / '.beta/skills/demo/SKILL.md'
        self.assertTrue(os.path.samefile(a, b))
        self.assertEqual(a.read_text(encoding='utf-8'), 'shared')
        self.assertEqual((b.parent / 'extra.txt').read_text(), 'preserve')
        self.assertTrue(os.path.samefile(self.home / '.alpha/AGENTS.md', self.shared / 'rules/AGENTS.md'))
        again = module.apply(self.home, self.shared, self.mam, 'common rules', self.clients)
        self.assertEqual(result['transaction'], again['transaction'])
        module.rollback(self.home, self.shared)
        self.assertEqual(a.read_text(encoding='utf-8'), 'shared')
        self.assertEqual(b.read_text(encoding='utf-8'), 'shared')
        self.assertEqual((self.home / '.alpha/AGENTS.md').read_text(), 'original alpha')
        self.assertEqual((self.home / '.beta/AGENTS.md').read_text(), 'original beta')

    def test_apply_refuses_skill_conflict_before_writing(self):
        (self.home / '.beta/skills/demo/SKILL.md').write_text('different', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'skill conflicts'):
            module.apply(self.home, self.shared, self.mam, 'rules', self.clients)
        self.assertFalse(self.shared.exists())
        self.assertEqual((self.home / '.alpha/AGENTS.md').read_text(), 'original alpha')

    def test_rollback_refuses_to_overwrite_changed_configuration(self):
        module.apply(self.home, self.shared, self.mam, 'common rules', self.clients)
        p = self.home / '.beta/INCLUDE.md'
        p.write_text('user edited', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            module.rollback(self.home, self.shared)
        self.assertEqual(p.read_text(), 'user edited')
        self.assertTrue(os.path.samefile(self.home / '.beta/skills/demo',
                                         self.shared / 'skills/demo'))

    def test_outside_home_refused(self):
        with self.assertRaises(ValueError):
            module.apply(self.home, Path(self.tmp.name) / 'outside', self.mam,
                         'rules', self.clients)

    def test_register_is_idempotent_and_rollback_preserves_source(self):
        module.apply(self.home, self.shared, self.mam, 'common rules', self.clients)
        source = self.shared / 'skills' / 'new-skill'
        source.mkdir(parents=True)
        (source / 'SKILL.md').write_text('new skill', encoding='utf-8')
        module.register(self.home, self.shared, self.mam, source, self.clients)
        module.register(self.home, self.shared, self.mam, source, self.clients)
        for host in ('alpha', 'beta'):
            self.assertTrue(os.path.samefile(self.home / f'.{host}/skills/new-skill', source))
        module.rollback(self.home, self.shared)
        self.assertEqual((source / 'SKILL.md').read_text(), 'new skill')
        for host in ('alpha', 'beta'):
            self.assertFalse((self.home / f'.{host}/skills/new-skill').exists())

    def test_unregistered_external_skill_link_refused(self):
        outside = Path(self.tmp.name) / 'external'
        outside.mkdir()
        (outside / 'SKILL.md').write_text('external', encoding='utf-8')
        link = self.home / '.alpha/skills/external'
        module.junction(link, outside)
        try:
            with self.assertRaisesRegex(ValueError, 'external skill link'):
                module.plan(self.home, self.shared, self.mam, self.clients)
        finally:
            os.rmdir(link) if os.name == 'nt' else link.unlink()

    def test_tree_files_runs_without_is_junction_on_python311(self):
        original = Path.is_junction if hasattr(Path, 'is_junction') else None
        try:
            if original is not None:
                delattr(Path, 'is_junction')
            self.assertEqual(module.tree_files(self.home / '.alpha/skills/demo'),
                             {'SKILL.md': module.digest(self.home / '.alpha/skills/demo/SKILL.md')})
        finally:
            if original is not None:
                Path.is_junction = original


if __name__ == '__main__':
    unittest.main()
