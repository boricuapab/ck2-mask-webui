import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from model_assets import REQUIRED_FILES, ensure_models, models_ready


class ModelDownloadTests(unittest.TestCase):
    def populate(self, root):
        for name in REQUIRED_FILES:
            path = root / 'models' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test asset')

    def test_first_inference_downloads_online_to_project_models(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            log = io.StringIO()
            with patch.dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1'):
                with patch('model_assets.subprocess.run', side_effect=lambda *a, **k: self.populate(root)) as run:
                    ensure_models(root, log)
            self.assertTrue(models_ready(root))
            args, kwargs = run.call_args
            self.assertEqual(args[0][-2:], ['--package_root', str(root / 'models')])
            self.assertEqual(kwargs['env']['HF_HUB_OFFLINE'], '0')
            self.assertEqual(kwargs['env']['TRANSFORMERS_OFFLINE'], '0')
            self.assertTrue(kwargs['check'])
            self.assertIn('Models ready', log.getvalue())

    def test_existing_models_do_not_access_network(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.populate(root)
            with patch('model_assets.subprocess.run') as run:
                ensure_models(root, io.StringIO())
            run.assert_not_called()

    def test_partial_snapshot_and_empty_weight_trigger_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self.populate(root)
            (root / 'models' / REQUIRED_FILES[0]).write_bytes(b'')
            (root / 'models/vfms/cradio/C-RADIOv4-SO400M/hf_model.py').unlink()
            self.assertFalse(models_ready(root))
            with patch('model_assets.subprocess.run', side_effect=lambda *a, **k: self.populate(root)) as run:
                ensure_models(root, io.StringIO())
            run.assert_called_once()
            self.assertTrue(models_ready(root))

    def test_failed_download_can_be_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch('model_assets.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'download')):
                with self.assertRaises(subprocess.CalledProcessError):
                    ensure_models(root, io.StringIO())
            self.assertFalse(models_ready(root))
            with patch('model_assets.subprocess.run', side_effect=lambda *a, **k: self.populate(root)):
                ensure_models(root, io.StringIO())
            self.assertTrue(models_ready(root))

    def test_incomplete_successful_download_fails_before_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('model_assets.subprocess.run'):
                with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                    ensure_models(Path(temp), io.StringIO())


if __name__ == '__main__':
    unittest.main()
