import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engine.model_variants import get_variant
from model_assets import ensure_models, models_ready, required_files


class ModelVariantTests(unittest.TestCase):
    def populate(self, root, variant):
        for name in required_files(variant):
            path = root/'models'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test asset')

    def test_int8_readiness_does_not_require_fp32_weights(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.populate(root, 'int8_convrot')
            self.assertTrue(models_ready(root, 'int8_convrot'))
            self.assertFalse(models_ready(root, 'fp32'))
            with patch('model_assets.subprocess.run') as run:
                ensure_models(root, io.StringIO(), variant='int8_convrot')
            run.assert_not_called()

    def test_missing_selected_model_invokes_variant_aware_downloader(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.populate(root, 'fp32')
            with patch('model_assets.subprocess.run', side_effect=lambda *a, **k: self.populate(root, 'int8_convrot')) as run:
                ensure_models(root, io.StringIO(), variant='int8_convrot')
            cmd = run.call_args.args[0]
            self.assertEqual(cmd[cmd.index('--model_variant')+1], 'int8_convrot')
            self.assertTrue(models_ready(root, 'int8_convrot'))

    def test_int8_downloads_only_selected_main_weights_and_shared_statistics(self):
        source = Path(__file__).resolve().parents[1]/'engine/scripts/download_weights.py'
        spec = importlib.util.spec_from_file_location('download_weights_test', source)
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        with tempfile.TemporaryDirectory() as temp, patch.object(script, 'hf_hub_download') as download:
            script.download_corridorkey(Path(temp), script.CORRIDORKEY_REPO, None, 'int8_convrot')
            filenames = [call.args[1] for call in download.call_args_list]
            self.assertEqual(filenames, ['corridorkey_v2_int8_convrot.safetensors', 'foundation_stats.safetensors'])
            self.assertEqual(download.call_args_list[0].args[0], 'boricuapab/corridorkey_v2_int8_convrot')
            self.assertEqual(download.call_args_list[0].kwargs['revision'], get_variant('int8_convrot')['revision'])

    def test_unknown_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            get_variant('../arbitrary-path')


if __name__ == '__main__':
    unittest.main()
