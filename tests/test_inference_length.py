"""Validate length settings and the actual queued inference command without a GPU."""
import ast
import asyncio
import json
import math
from pathlib import Path
import queue
import sys
import tempfile
import time
import unittest
import uuid

from inference_length import resolve_length
from chunk_settings import validate_chunk
from engine.model_variants import get_variant
from engine.hint_frames import validate_hint_frame
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


class ApiError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        super().__init__(detail)


class InferenceLengthTests(unittest.TestCase):
    def test_full_shot_ignores_inactive_inputs(self):
        self.assertEqual(resolve_length('full', '', '', 24)['num_frames'], -1)
        self.assertEqual(resolve_length('full', 'invalid', 'invalid', 24)['num_frames'], -1)

    def test_frames_and_seconds_at_different_rates(self):
        self.assertEqual(resolve_length('frames', '120', '', 24)['num_frames'], 120)
        for duration, fps, expected in [('5', 24, 120), ('5', 60, 300),
                                         ('1', 29.97, 30), ('.07', 100, 7),
                                         ('.001', 24, 1)]:
            with self.subTest(seconds=duration, fps=fps):
                self.assertEqual(resolve_length('seconds', '', duration, fps)['num_frames'], expected)

    def test_invalid_limits_are_rejected(self):
        for mode, frames, seconds in [('unknown', '', ''), ('frames', '0', ''),
                                      ('frames', '-1', ''), ('frames', '1.5', ''),
                                      ('frames', '', ''), ('seconds', '', '0'),
                                      ('seconds', '', '-1'), ('seconds', '', 'nan'),
                                      ('seconds', '', 'inf'), ('seconds', '', '')]:
            with self.subTest(mode=mode, frames=frames, seconds=seconds):
                with self.assertRaises(ValueError):
                    resolve_length(mode, frames, seconds, 24)
        with self.assertRaises(ValueError):
            resolve_length('seconds', '', '1', 0)

    def test_create_job_passes_limit_to_engine_and_saves_history(self):
        tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
        endpoint = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'create_job')
        endpoint.decorator_list = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'inputs').mkdir()
            (root / 'outputs').mkdir()
            project = root / 'project.json'
            project.write_text('{}')
            source = root / 'sample.mp4'
            source.touch()
            hint_image = root/'mask.png'
            Image.new('L', (320, 240), 255).save(hint_image)
            ns = dict(ROOT=root, INPUTS=root/'inputs', MODELS=root/'models', Path=Path, sys=sys, time=time,
                      uuid=uuid, json=json, jobs={}, pending=queue.Queue(),
                      project_path=lambda pid: project,
                      asset_path=lambda aid, **kwargs: hint_image if aid == 'image' else source,
                      get_ui_state=lambda pid: {}, resolve_length=resolve_length, validate_chunk=validate_chunk,
                      get_variant=get_variant,
                      validate_hint_frame=validate_hint_frame, math=math,
                      probe=lambda path: dict(width=320, height=240, fps=30, duration=10),
                      HTTPException=ApiError, UploadFile=type('UploadFile', (), {}),
                      File=lambda value: value, Form=lambda value: value)
            exec(compile(ast.Module(body=[endpoint], type_ignores=[]), 'app.py', 'exec'), ns)
            for mode, frames, seconds, expected in [('full', '', '', -1),
                                                    ('frames', '45', '', 45),
                                                    ('seconds', '', '2.5', 75),
                                                    ('frames', '10000', '', 10000)]:
                job = asyncio.run(ns['create_job'](saved_source='source', length_mode=mode,
                                                 frame_count=frames, seconds=seconds))
                jid, cmd, out = ns['pending'].get_nowait()
                self.assertEqual(cmd[cmd.index('--num_frames')+1], str(expected))
                self.assertEqual(cmd[cmd.index('--start_mode')+1], 'begin')
                saved = json.loads((out / 'job.json').read_text())
                self.assertEqual(saved['processing_length'], job['processing_length'])
                self.assertEqual(saved['processing_length']['mode'], mode)
                self.assertEqual(job['model_variant'], 'fp32')
                self.assertTrue(cmd[cmd.index('--weights')+1].endswith('corridorkey_v2.safetensors'))
                self.assertEqual(cmd[cmd.index('--despill_strength')+1], '0.5')
            job = asyncio.run(ns['create_job'](saved_source='source', model_variant='int8_convrot'))
            _, cmd, _ = ns['pending'].get_nowait()
            self.assertEqual(job['model_variant'], 'int8_convrot')
            self.assertTrue(cmd[cmd.index('--weights')+1].endswith('corridorkey_v2_int8_convrot.safetensors'))
            for strength in (0, .1, 1):
                job = asyncio.run(ns['create_job'](saved_source='source', despill_strength=strength))
                _, cmd, out = ns['pending'].get_nowait()
                self.assertEqual(float(cmd[cmd.index('--despill_strength')+1]), strength)
                self.assertEqual(json.loads((out/'job.json').read_text())['despill_strength'], strength)
            for strength in (-.1, 1.1, float('nan'), float('inf')):
                with self.subTest(strength=strength), self.assertRaises(ApiError) as error:
                    asyncio.run(ns['create_job'](saved_source='source', despill_strength=strength))
                self.assertEqual(error.exception.status_code, 400)
            job = asyncio.run(ns['create_job'](saved_source='source', saved_hint_image='image',
                                              hint_frame=61, length_mode='seconds', seconds='2.5'))
            _, cmd, _ = ns['pending'].get_nowait()
            self.assertEqual(cmd[cmd.index('--hint_frame_index')+1], '60')
            self.assertEqual(cmd[cmd.index('--hint_first_frame')+1], str(hint_image))
            self.assertTrue(job['hinted'])
            self.assertEqual(job['hint_label'], 'PNG hint · frame 61')
            for frame in (0, 76):
                with self.subTest(frame=frame), self.assertRaises(ApiError):
                    asyncio.run(ns['create_job'](saved_source='source', saved_hint_image='image',
                                                hint_frame=frame, length_mode='seconds', seconds='2.5'))
            Image.new('L', (100, 100)).save(hint_image)
            with self.assertRaises(ApiError) as mismatch:
                asyncio.run(ns['create_job'](saved_source='source', saved_hint_image='image'))
            self.assertIn('dimensions', str(mismatch.exception))
            before = ns['pending'].qsize()
            with self.assertRaises(ApiError) as error:
                asyncio.run(ns['create_job'](saved_source='source', length_mode='frames', frame_count='0'))
            self.assertEqual(error.exception.status_code, 400)
            self.assertEqual(ns['pending'].qsize(), before)


if __name__ == '__main__':
    unittest.main()
