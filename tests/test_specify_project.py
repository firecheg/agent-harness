import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('specify_project',ROOT/'execution/specify_project.py')
sp=importlib.util.module_from_spec(spec);spec.loader.exec_module(sp)


class SpecifyProject(unittest.TestCase):
    @unittest.skipUnless(shutil.which('specify'),'установите specify-cli 1.0.4')
    def test_specify_preview_repeat_and_user_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            first=sp.initialize(root)
            self.assertTrue(first['new']);self.assertFalse(list(root.iterdir()))
            self.assertTrue(sp.initialize(root,True)['applied'])
            self.assertEqual(sp.initialize(root,True)['new'],[])
            target=root/'.claude/skills/speckit-plan/SKILL.md'
            target.write_text('user change',encoding='utf-8')
            with self.assertRaises(ValueError):sp.initialize(root,True)
            self.assertEqual(target.read_text(encoding='utf-8'),'user change')


if __name__=='__main__':unittest.main()
