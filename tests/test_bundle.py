import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'install-node.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {}
        for name in ['setup.sh', 'manage.py', 'install-node.py', 'mediamtx', 'ffprobe',
                     'node-runtime.tar.xz', 'coturn-source.tar.gz', 'agent/agent.mjs',
                     'agent/screen-relay.mjs', 'agent/media-probe.mjs', 'licenses/MEDIAMTX-LICENSE.txt']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
            self.files[name] = hashlib.sha256(b'fixture').hexdigest()
        self.manifest()

    def manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps({'version':'2.1.3', 'files':self.files}))

    def test_valid_bundle_and_tampering(self):
        self.assertEqual(module.verify_bundle(self.root)['version'], '2.1.3')
        (self.root / 'agent/media-probe.mjs').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            module.verify_bundle(self.root)

    def test_missing_media_probe_rejected(self):
        del self.files['agent/media-probe.mjs']
        self.manifest()
        with self.assertRaises(ValueError):
            module.verify_bundle(self.root)

    def test_parent_escape_rejected(self):
        self.files['../outside'] = hashlib.sha256(b'fixture').hexdigest()
        self.manifest()
        with self.assertRaises(ValueError):
            module.verify_bundle(self.root)

    def test_control_config_remains_loopback_and_turn_authenticated(self):
        turn = module.turn_config({'publicHost':'8.8.8.8','turnSecret':'3'*64}, '10.0.0.2')
        self.assertIn('\nuse-auth-secret\n', turn)
        self.assertIn('\nbps-capacity=0\n', turn)
        self.assertIn('\nmax-bps=65536\n', turn)
        self.assertIn('\ndenied-peer-ip=127.0.0.0-127.255.255.255\n', turn)
        source = (ROOT / 'install-node.py').read_text(encoding='utf-8')
        for value in ['127.0.0.1:9997','127.0.0.1:9998','127.0.0.1:8554']:
            self.assertIn(value, source)

if __name__ == '__main__':
    unittest.main()
