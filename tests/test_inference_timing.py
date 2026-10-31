"""Exercise render timing without starting the app or downloading model weights."""
import ast
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


class InferenceTimingTests(unittest.TestCase):
    def test_elapsed_time_is_saved_and_logged_after_download(self):
        source = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
        worker = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'worker')
        for return_code in (0, 1):
            with self.subTest(return_code=return_code), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                out = root / 'outputs' / 'testjob'
                out.mkdir(parents=True)
                events = []
                pending = Mock()
                pending.get.side_effect = [('testjob', ['inference'], out), StopIteration]
                process = Mock()
                process.wait.return_value = return_code
                subprocess_mock = Mock()
                subprocess_mock.STDOUT = subprocess.STDOUT
                subprocess_mock.Popen.return_value = process
                clock = Mock()
                readings = iter((10.0, 75.25))
                clock.perf_counter.side_effect = lambda: (events.append('timer'), next(readings))[1]
                download = Mock(side_effect=lambda *args, **kwargs: events.append('download'))
                control = Mock()
                control.lock = threading.RLock()
                control.run.return_value = subprocess.CompletedProcess(['inference'], return_code)
                jobs = {'testjob': {'id': 'testjob'}}
                def save_job(job):
                    (out / 'job.json').write_text(json.dumps(job), encoding='utf-8')
                namespace = dict(ROOT=root, jobs=jobs, pending=pending, time=clock,
                                 models_ready=Mock(return_value=False), ensure_models=download,
                                 os=os, json=json, subprocess=subprocess_mock,
                                 job_control=control, save_job=save_job, JobStopped=RuntimeError)
                exec(compile(ast.Module(body=[worker], type_ignores=[]), 'app.py', 'exec'), namespace)
                with self.assertRaises(StopIteration):
                    namespace['worker']()
                record = json.loads((out / 'job.json').read_text(encoding='utf-8'))
                self.assertEqual(record['inference_seconds'], 65.25)
                self.assertEqual(record['status'], 'complete' if return_code == 0 else 'failed')
                self.assertEqual(events, ['download', 'timer', 'timer'])
                log = (out / 'inference.log').read_text(encoding='utf-8')
                self.assertIn('65.25 seconds', log)
                self.assertIn('excluding queue wait and model downloads', log)
                pending.task_done.assert_called_once()


if __name__ == '__main__':
    unittest.main()
