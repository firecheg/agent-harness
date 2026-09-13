import importlib.util
import ctypes
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ctypes import wintypes

spec = importlib.util.spec_from_file_location(
    'client_adapters', Path(__file__).resolve().parents[1] / 'execution/client_adapters.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

shared_spec = importlib.util.spec_from_file_location(
    'shared_harness_for_adapter_tests', Path(__file__).resolve().parents[1] / 'execution/shared_harness.py')
shared_module = importlib.util.module_from_spec(shared_spec)
shared_spec.loader.exec_module(shared_module)


def clients():
    return {
        'jsonclient': {
            'mcp': {'format': 'json', 'path': '.jsonclient/config.json',
                    'keys': ['mcpServers', 'agent_harness']},
            'hook': {'format': 'json', 'path': '.jsonclient/settings.json',
                     'keys': ['hooks', 'PreToolUse'], 'matcher': 'Read'},
        },
        'tomlclient': {
            'mcp': {'format': 'config_fragment', 'path': '.tomlclient/config.toml',
                    'marker': 'agent-harness',
                    'template': '[mcp_servers.{name}]\ncommand = {command_json}\n'
                                'args = {args_json}\n[mcp_servers.{name}.env]\n{env_lines}'},
        },
    }


def _short_path(path):
    if os.name != 'nt':
        return None
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    get_short = kernel32.GetShortPathNameW
    get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_short(str(path), buffer, len(buffer))
    return Path(buffer.value) if length else None


class AdapterTests(unittest.TestCase):
    def test_equivalent_windows_short_path_is_accepted(self):
        if os.name != 'nt':
            self.skipTest('8.3 paths are Windows-specific')
        with tempfile.TemporaryDirectory(prefix='agent harness long path ') as tmp:
            long_home = Path(tmp)
            short_home = _short_path(long_home)
            if not short_home or short_home == long_home:
                self.skipTest('temporary path has no 8.3 alias')
            state = m.configure(short_home, short_home / '.agent-harness',
                                short_home / 'mam', 'python',
                                {'third': clients()['tomlclient']})
            self.assertEqual(state['status'], 'active')
            self.assertEqual(m.issues(short_home / '.agent-harness'), [])

    def test_managed_settings_idempotent_rollback_preserves_other_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            shared = home / '.agent-harness'
            mam = home / 'mam'
            original_toml = 'model = "original"\n'
            (home / '.tomlclient').mkdir()
            (home / '.tomlclient/config.toml').write_text(original_toml)
            m.configure(home, shared, mam, 'python.exe', clients())
            m.configure(home, shared, mam, 'python.exe', clients())
            data = m.load(home / '.jsonclient/config.json')
            data['other'] = 'new'
            m.write(home / '.jsonclient/config.json', data)
            self.assertEqual(m.issues(shared), [])
            m.rollback(shared, home)
            self.assertEqual(m.load(home / '.jsonclient/config.json')['other'], 'new')
            self.assertIsNone(m.get(m.load(home / '.jsonclient/config.json'),
                                    ['mcpServers', 'agent_harness']))
            self.assertEqual(m.load(home / '.jsonclient/settings.json'), {})
            self.assertEqual((home / '.tomlclient/config.toml').read_text(), original_toml)

    def test_fresh_generic_fragment_creates_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            state = m.configure(home, home / '.agent-harness', home / 'mam', 'python',
                                {'third': clients()['tomlclient']})
            self.assertEqual(state['status'], 'active')
            self.assertIn('agent_harness', (home / '.tomlclient/config.toml').read_text())

    def test_preexisting_server_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / '.jsonclient').mkdir()
            m.write(home / '.jsonclient/config.json',
                    {'mcpServers': {'agent_harness': {'command': 'custom'}}})
            with self.assertRaisesRegex(ValueError, 'pre-existing'):
                m.configure(home, home / '.agent-harness', home / 'mam', 'python', clients())
            self.assertEqual(m.load(home / '.jsonclient/config.json')['mcpServers']['agent_harness'],
                             {'command': 'custom'})

    def test_preexisting_fragment_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = home / '.tomlclient/config.toml'
            path.parent.mkdir()
            path.write_text('# BEGIN agent-harness managed: agent-harness\ncustom\n'
                            '# END agent-harness managed: agent-harness\n')
            with self.assertRaisesRegex(ValueError, 'pre-existing'):
                m.configure(home, home / '.agent-harness', home / 'mam', 'python',
                            {'third': clients()['tomlclient']})
            self.assertIn('custom', path.read_text())

    def test_interrupted_configuration_can_be_rolled_back_and_retried(self):
        for resume in (False, True):
            with self.subTest(resume=resume), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                shared = home / '.agent-harness'
                json_path = home / '.jsonclient/config.json'
                original_write = m.write

                def interrupt_after_first_setting(path, value):
                    original_write(path, value)
                    if Path(path).resolve() == json_path.resolve():
                        raise KeyboardInterrupt('simulated process interruption')

                with patch.object(m, 'write', side_effect=interrupt_after_first_setting):
                    with self.assertRaises(KeyboardInterrupt):
                        m.configure(home, shared, home / 'mam', 'python', clients())
                self.assertEqual(m.load(shared / 'adapters.json')['status'], 'applying')
                if resume:
                    m.configure(home, shared, home / 'mam', 'python', clients())
                    self.assertEqual(m.issues(shared), [])
                m.rollback(shared, home)
                self.assertIsNone(m.get(m.load(json_path), ['mcpServers', 'agent_harness']))
                self.assertEqual(m.load(home / '.jsonclient/settings.json'), {})

    def test_partial_recovery_refuses_changed_managed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            shared = home / '.agent-harness'
            m.configure(home, shared, home / 'mam', 'python', clients())
            state = m.load(shared / 'adapters.json')
            state['status'] = 'applying'
            m.write(shared / 'adapters.json', state)
            settings = home / '.jsonclient/settings.json'
            data = m.load(settings)
            data['hooks']['PreToolUse'] = [{'user': 'changed'}]
            m.write(settings, data)
            original = (home / '.jsonclient/config.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'changed managed setting'):
                m.rollback(shared, home)
            self.assertEqual((home / '.jsonclient/config.json').read_bytes(), original)
            self.assertEqual(m.load(settings), data)

    def test_junction_parent_escape_is_rejected_before_state_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / 'home'
            outside = root / 'outside'
            home.mkdir()
            outside.mkdir()
            link = home / '.third'
            shared_module.junction(link, outside)
            try:
                manifest = {'third': {'mcp': {'format': 'json', 'path': '.third/config.json',
                                               'keys': ['mcpServers', 'agent_harness']}}}
                with self.assertRaisesRegex(ValueError, 'escapes home'):
                    m.configure(home, home / '.agent-harness', home / 'mam', 'python', manifest)
                self.assertFalse((outside / 'config.json').exists())
                self.assertFalse((home / '.agent-harness').exists())
            finally:
                os.rmdir(link) if os.name == 'nt' else link.unlink()

    def test_state_path_is_preflighted_before_configure(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            calls = []
            original = m._safe_path

            def record(path, root, label):
                calls.append((Path(path), label))
                return original(path, root, label)

            with patch.object(m, '_safe_path', side_effect=record):
                m.configure(home, home / '.agent-harness', home / 'mam', 'python',
                            {'third': clients()['tomlclient']})
            state_path = home / '.agent-harness/adapters.json'
            self.assertIn((state_path.resolve(), 'adapter state'),
                          [(path.resolve(), label) for path, label in calls])

    def test_state_file_symlink_escape_is_rejected_when_supported(self):
        if os.name == 'nt':
            self.skipTest('Windows test environment may deny file symlink creation')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / 'home'
            home.mkdir()
            shared = home / '.agent-harness'
            shared.mkdir()
            outside = root / 'outside.json'
            outside.write_text('{}', encoding='utf-8')
            state_path = shared / 'adapters.json'
            try:
                os.symlink(outside, state_path)
            except OSError as exc:
                self.skipTest(f'file symlinks unavailable: {exc}')
            with self.assertRaisesRegex(ValueError, 'adapter state'):
                m.configure(home, shared, home / 'mam', 'python',
                            {'third': clients()['tomlclient']})
            with self.assertRaisesRegex(ValueError, 'adapter state'):
                m.rollback(shared, home)
            self.assertEqual(outside.read_text(encoding='utf-8'), '{}')


if __name__ == '__main__':
    unittest.main()
