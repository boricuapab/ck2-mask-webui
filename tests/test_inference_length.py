"""Validate length settings and the actual queued inference command without a GPU."""
import ast
import asyncio
import json
from pathlib import Path
import queue
import sys
import tempfile
import time
import unittest
import uuid

from inference_length import resolve_length

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
            ns = dict(ROOT=root, INPUTS=root/'inputs', Path=Path, sys=sys, time=time,
                      uuid=uuid, json=json, jobs={}, pending=queue.Queue(),
                      project_path=lambda pid: project, asset_path=lambda aid: source,
                      get_ui_state=lambda pid: {}, resolve_length=resolve_length,
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
            before = ns['pending'].qsize()
            with self.assertRaises(ApiError) as error:
                asyncio.run(ns['create_job'](saved_source='source', length_mode='frames', frame_count='0'))
            self.assertEqual(error.exception.status_code, 400)
            self.assertEqual(ns['pending'].qsize(), before)


if __name__ == '__main__':
    unittest.main()
