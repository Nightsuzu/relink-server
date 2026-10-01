import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT
spec = importlib.util.spec_from_file_location('manager', SOURCE / 'manage.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.setup = dict(version=1, nodeId='1'*32, token='2'*64, turnSecret='3'*64,
                          publicHost='8.8.8.8', capacityMbps=100, serverUrl='wss://relinkus.cn/relink/ws')
        self.path = self.directory / 'relink-node-setup.json'
        self.path.write_text(json.dumps(self.setup), encoding='utf-8-sig')

    def test_config_with_bom_and_ignores_arbitrary_runtime_overrides(self):
        self.path.write_text(json.dumps(dict(self.setup, apiUrl='http://evil.example', authPort=80)), encoding='utf-8-sig')
        self.assertEqual(m.load_setup(self.path), self.setup)

    def test_bad_credentials_dont_appear_in_error(self):
        secret = 'a-secret-that-must-not-appear'
        self.path.write_text(json.dumps(dict(self.setup, token=secret)))
        with self.assertRaises(ValueError) as raised:
            m.load_setup(self.path)
        self.assertNotIn(secret, str(raised.exception))

    def test_wrong_coordinator_or_node_rejected(self):
        for change in [dict(serverUrl='wss://47.98.132.62/relink/ws'), dict(nodeId=''), dict(publicHost='127.0.0.1'), dict(capacityMbps=0)]:
            self.path.write_text(json.dumps(dict(self.setup, **change)))
            with self.assertRaises(ValueError):
                m.load_setup(self.path)

    def test_oversized_config_rejected(self):
        self.path.write_text(' '*9000)
        with self.assertRaises(ValueError):
            m.load_setup(self.path)

    def test_duplicate_install_preserves_all_files(self):
        prefix = self.directory / 'installed'
        (prefix / 'config').mkdir(parents=True)
        (prefix / 'config/agent.json').write_text(json.dumps(self.setup))
        (prefix / 'install-complete.json').write_text('{"version":"2.1.3"}')
        before = {p: p.read_bytes() for p in prefix.rglob('*') if p.is_file()}
        with patch.object(m, 'PREFIX', prefix):
            self.assertTrue(m.installed_matches(self.setup))
            with self.assertRaises(ValueError):
                m.installed_matches(dict(self.setup, nodeId='4'*32))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_partial_install_is_not_overwritten(self):
        with patch.object(m, 'PREFIX', self.directory):
            with self.assertRaises(ValueError):
                m.installed_matches(self.setup)

    def test_existing_old_version_is_not_claimed_complete(self):
        (self.directory / 'config').mkdir()
        (self.directory / 'config/agent.json').write_text(json.dumps(self.setup))
        with patch.object(m, 'PREFIX', self.directory):
            with self.assertRaises(ValueError):
                m.installed_matches(self.setup)

    def test_default_config_lookup(self):
        with patch.object(m.Path, 'cwd', return_value=self.directory):
            self.assertEqual(m.resolve_setup(None), self.path)

    def test_another_version_is_not_overwritten(self):
        prefix = self.directory / 'installed'
        (prefix / 'config').mkdir(parents=True)
        (prefix / 'config/agent.json').write_text(json.dumps(self.setup))
        (prefix / 'install-complete.json').write_text('{"version":"2.1.2"}')
        with patch.object(m, 'PREFIX', prefix):
            with self.assertRaises(ValueError):
                m.installed_matches(self.setup)

    def test_malformed_install_record_is_rejected(self):
        prefix = self.directory / 'installed'
        (prefix / 'config').mkdir(parents=True)
        (prefix / 'config/agent.json').write_text(json.dumps(self.setup))
        stamp = prefix / 'install-complete.json'
        with patch.object(m, 'PREFIX', prefix):
            for contents in ['not json', '[]', '{}']:
                stamp.write_text(contents)
                with self.assertRaises(ValueError):
                    m.installed_matches(self.setup)

    def test_plan_never_runs_preflight_or_installs(self):
        with patch.object(m, 'resolve_setup', return_value=self.path), patch.object(m, 'preflight', side_effect=AssertionError('must not install')):
            with patch.object(m, 'installer') as factory, patch('sys.argv', ['manage.py', 'plan']):
                self.assertEqual(m.main(), 0)
                factory.return_value.verify_bundle.assert_called_once()

if __name__ == '__main__':
    unittest.main()
