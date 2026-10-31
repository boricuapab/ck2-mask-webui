import unittest
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from unittest.mock import Mock

from chunk_settings import CHUNK_CHOICES, apply_chunk, suggest_chunk, validate_chunk


class ChunkSettingsTests(unittest.TestCase):
    def info(self, width=1280, height=720, duration=30, fps=24):
        return dict(width=width, height=height, duration=duration, fps=fps)

    def test_16gb_720p_uses_conservative_24_frame_window(self):
        result = suggest_chunk(self.info(), {'num_frames': -1}, 14.8, 16)
        self.assertEqual(result['chunk'], 24)
        self.assertEqual(result['stride'], 12)
        self.assertFalse(result['low_vram'])
        self.assertEqual((result['padded_width'], result['padded_height']), (1280, 768))
        self.assertTrue(result['fits'])

    def test_resolution_and_available_memory_reduce_suggestion(self):
        normal = suggest_chunk(self.info(), {'num_frames': -1}, 14.8, 16)
        high_res = suggest_chunk(self.info(3840, 2160), {'num_frames': -1}, 14.8, 16)
        busy_gpu = suggest_chunk(self.info(), {'num_frames': -1}, 8, 16)
        self.assertLess(high_res['chunk'], normal['chunk'])
        self.assertLess(busy_gpu['chunk'], normal['chunk'])

    def test_short_source_and_selected_frame_limit_cap_windows(self):
        for info, length, limit in [(self.info(), {'num_frames': 5}, 5),
                                   (self.info(duration=.1), {'num_frames': -1}, 3)]:
            result = suggest_chunk(info, length, 24, 24)
            self.assertLessEqual(result['chunk'], limit)
            self.assertLessEqual(result['frames'], limit)

    def test_low_memory_fallback_is_flagged(self):
        result = suggest_chunk(self.info(), {'num_frames': -1}, 1, 16)
        self.assertEqual(result['chunk'], 1)
        self.assertTrue(result['low_vram'])
        self.assertFalse(result['fits'])

    def test_manual_settings_reach_engine_and_short_clip_is_capped(self):
        job = dict(metadata=self.info(), processing_length={'num_frames': 12},
                   chunk_size='32', low_vram=True)
        cmd = ['inference']
        apply_chunk(job, cmd, dict(free_gib=14.8, total_gib=16))
        self.assertEqual(cmd, ['inference', '--hann_chunk', '12', '--hann_stride', '6', '--low_vram'])
        self.assertFalse(job['chunk_settings']['automatic'])

    def test_automatic_is_recomputed_using_current_memory(self):
        job = dict(metadata=self.info(), chunk_size='auto')
        apply_chunk(job, [], dict(free_gib=14.8, total_gib=16))
        first = job['chunk_settings']['chunk']
        apply_chunk(job, [], dict(free_gib=8, total_gib=16))
        self.assertLess(job['chunk_settings']['chunk'], first)

    def test_validation_rejects_arbitrary_or_invalid_values(self):
        self.assertEqual(validate_chunk('auto'), 'auto')
        for value in CHUNK_CHOICES:
            self.assertEqual(validate_chunk(str(value)), value)
        for value in ('0', '-1', '8.5', '9999', 'bad', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_chunk(value)

    def test_worker_applies_recommendation_before_launch_and_logs_settings(self):
        root_source = Path(__file__).resolve().parents[1]
        tree = ast.parse((root_source/'app.py').read_text(encoding='utf-8'))
        worker = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'worker')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root/'outputs/job'
            out.mkdir(parents=True)
            cmd = ['inference']
            pending = Mock()
            pending.get.side_effect = [('job', cmd, out), StopIteration]
            control = Mock()
            control.lock = threading.RLock()
            control.run.return_value = subprocess.CompletedProcess(cmd, 0)
            job = dict(id='job', metadata=self.info(), chunk_size='auto')
            def save_job(record):
                (out/'job.json').write_text(json.dumps(record))
            ns = dict(ROOT=root, jobs={'job': job}, pending=pending, job_control=control,
                      os=os, subprocess=subprocess, time=time, models_ready=lambda root: True,
                      gpu_memory=lambda: dict(free_gib=14.8, total_gib=16), apply_chunk=apply_chunk,
                      save_job=save_job, JobStopped=RuntimeError)
            exec(compile(ast.Module(body=[worker], type_ignores=[]), 'app.py', 'exec'), ns)
            with self.assertRaises(StopIteration):
                ns['worker']()
            self.assertEqual(cmd[-4:], ['--hann_chunk', '24', '--hann_stride', '12'])
            record = json.loads((out/'job.json').read_text())
            self.assertEqual(record['chunk_settings']['chunk'], 24)
            self.assertTrue(record['chunk_settings']['automatic'])
            self.assertIn('Temporal chunk: 24 frames', (out/'inference.log').read_text())


if __name__ == '__main__':
    unittest.main()
