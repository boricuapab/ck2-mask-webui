import ast
import asyncio
import io
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

from PIL import Image
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'engine'))
from hint_frames import inject_frame_hint, validate_hint_frame
from corridorkey.video_io import load_initial_hint_frame


class ApiError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        super().__init__(detail)


class Upload:
    def __init__(self, content, filename='mask.png'):
        self.content = io.BytesIO(content)
        self.filename = filename

    async def read(self, size):
        return self.content.read(size)

    async def close(self):
        self.content.close()


class PngHintTests(unittest.TestCase):
    def test_frame_numbering_and_selected_range(self):
        self.assertEqual(validate_hint_frame(1, 100, -1), 0)
        self.assertEqual(validate_hint_frame(100, 100, -1), 99)
        self.assertEqual(validate_hint_frame(20, 100, 20), 19)
        for frame in (0, 21, 101):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                validate_hint_frame(frame, 100, 20)

    def test_correct_frame_in_every_overlapping_window_overrides_carry(self):
        image = torch.ones((1, 2, 2))
        for start, end, applies in ((0, 4, False), (2, 6, True), (4, 8, True), (6, 10, False)):
            hints = torch.zeros((1, 4, 1, 2, 2), dtype=torch.bfloat16)
            quality = torch.full((1, 4), .25)
            present = torch.zeros((1, 4), dtype=torch.bool)
            self.assertEqual(inject_frame_hint(hints, quality, present, image, 4, start, end, .95), applies)
            self.assertEqual(present.sum().item(), int(applies))
            if applies:
                offset = 4-start
                torch.testing.assert_close(hints[0, offset].float(), image)
                self.assertAlmostEqual(quality[0, offset].item(), .95, places=5)
                self.assertEqual(hints.sum().item(), 4)

    def test_png_alpha_and_padding_match_video(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'mask.png'
            Image.new('RGBA', (320, 240), (0, 255, 0, 128)).save(path)
            meta = dict(native_hw=(240, 320), model_native_hw=(240, 320),
                        shape_hw=(256, 384), pad=(32, 32, 8, 8), hint_frame_index=4)
            hint = load_initial_hint_frame(str(path), meta)
            self.assertEqual(tuple(hint.shape), (1, 256, 384))
            self.assertAlmostEqual(hint.float().mean().item(), 128/255, delta=.003)

    def test_png_upload_verifies_image_and_returns_dimensions(self):
        tree = ast.parse((ROOT/'app.py').read_text(encoding='utf-8'))
        endpoint = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'upload_hint_image')
        endpoint.decorator_list = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ns = dict(INPUTS=root, uuid=uuid, Path=Path, HTTPException=ApiError,
                      UploadFile=Upload, File=lambda value: value)
            exec(compile(ast.Module(body=[endpoint], type_ignores=[]), 'app.py', 'exec'), ns)
            data = io.BytesIO()
            Image.new('L', (320, 240), 255).save(data, format='PNG')
            asset = asyncio.run(ns['upload_hint_image'](Upload(data.getvalue())))
            self.assertEqual((asset['width'], asset['height'], asset['kind']), (320, 240, 'png'))
            self.assertTrue((root/asset['id']/'hint.png').is_file())
            for upload in (Upload(b'invalid'), Upload(data.getvalue(), 'mask.jpg')):
                with self.assertRaises(ApiError) as error:
                    asyncio.run(ns['upload_hint_image'](upload))
                self.assertEqual(error.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()
