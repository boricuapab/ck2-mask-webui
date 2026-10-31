"""Run real subprocess cancellation and queue tests without models or a GPU."""
import ast
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import psutil

from job_control import JobControl, JobStopped

ROOT = Path(__file__).resolve().parents[1]


class ApiError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        super().__init__(detail)


class WorkerQueue(queue.Queue):
    def get(self, *args, **kwargs):
        item = super().get(*args, **kwargs)
        if item is None:
            self.task_done()
            raise SystemExit()
        return item


def functions(root, controller):
    names = {'save_job', 'get_job', 'stop_job', 'clear_job', 'worker', 'list_jobs'}
    tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    namespace = dict(ROOT=root, jobs={}, pending=WorkerQueue(), job_control=controller,
                     ACTIVE_JOB_STATUSES={'queued', 'downloading', 'running', 'stopping'},
                     os=os, json=json, time=time, subprocess=subprocess, JobStopped=JobStopped,
                     HTTPException=ApiError, models_ready=lambda root, **kwargs: True,
                     gpu_memory=lambda: {'free_gib': 14.8}, apply_chunk=lambda *args: {'fits': True})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'app.py', 'exec'), namespace)
    return namespace


def wait_for(predicate):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for render state')


class JobControlTests(unittest.TestCase):
    def test_cancel_before_start_never_launches_process(self):
        controller = JobControl()
        controller.cancel('cancelled')
        with self.assertRaises(JobStopped):
            controller.run('cancelled', ['this-command-must-not-run'])

    def test_stop_during_model_download_prevents_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / 'outputs/download'
            out.mkdir(parents=True)
            marker = root / 'downloading'
            controller = JobControl()
            ns = functions(root, controller)
            ns['models_ready'] = lambda root, **kwargs: False
            def download(root, log, runner, **kwargs):
                runner([sys.executable, '-c',
                        'from pathlib import Path; import sys,time; Path(sys.argv[1]).touch(); time.sleep(60)',
                        str(marker)], stdout=log, stderr=subprocess.STDOUT, check=True)
            ns['ensure_models'] = download
            ns['jobs']['download'] = dict(id='download', status='queued', files=[])
            ns['save_job'](ns['jobs']['download'])
            ns['pending'].put(('download', ['inference-must-not-start'], out))
            thread = threading.Thread(target=ns['worker'], daemon=True)
            thread.start()
            try:
                wait_for(marker.exists)
                self.assertEqual(ns['jobs']['download']['status'], 'downloading')
                ns['stop_job']('download')
                wait_for(lambda: ns['pending'].unfinished_tasks == 0)
                self.assertEqual(ns['jobs']['download']['status'], 'stopped')
                self.assertNotIn('inference_seconds', ns['jobs']['download'])
            finally:
                controller.cancel('download')
                ns['pending'].put(None)
                thread.join(timeout=2)

    def test_stop_kills_child_encoder_and_next_job_completes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'engine').mkdir()
            controller = JobControl()
            ns = functions(root, controller)
            child_file = root / 'child.pid'
            script = ('import subprocess,sys,time; from pathlib import Path; '
                      'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                      'Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)')
            for jid, cmd in [('first', [sys.executable, '-c', script, str(child_file)]),
                             ('second', [sys.executable, '-c', 'print("next render finished")'])]:
                out = root / 'outputs' / jid
                out.mkdir(parents=True)
                ns['jobs'][jid] = dict(id=jid, status='queued', files=[])
                ns['save_job'](ns['jobs'][jid])
                ns['pending'].put((jid, cmd, out))
            thread = threading.Thread(target=ns['worker'], daemon=True)
            thread.start()
            try:
                wait_for(child_file.exists)
                child_pid = int(child_file.read_text())
                with self.assertRaises(ApiError) as error:
                    ns['clear_job']('first')
                self.assertEqual(error.exception.status_code, 409)
                ns['stop_job']('first')
                wait_for(lambda: ns['jobs']['second']['status'] == 'complete')
                wait_for(lambda: ns['pending'].unfinished_tasks == 0)
                self.assertFalse(psutil.pid_exists(child_pid))
                self.assertEqual(ns['jobs']['first']['status'], 'stopped')
                self.assertIn('inference_seconds', ns['jobs']['first'])
                self.assertIn('stopped by user', (root / 'outputs/first/inference.log').read_text())
                ns['clear_job']('first')
                self.assertEqual([j['id'] for j in ns['list_jobs']()], ['second'])
                # Simulate restarting: reload history from disk, with no in-memory jobs.
                ns['jobs'].clear()
                self.assertEqual([j['id'] for j in ns['list_jobs']()], ['second'])
                self.assertTrue((root / 'outputs/first/inference.log').is_file())
            finally:
                controller.cancel('first')
                controller.cancel('second')
                ns['pending'].put(None)
                thread.join(timeout=2)

    def test_queued_stop_clear_and_stale_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            controller = JobControl()
            ns = functions(root, controller)
            out = root / 'outputs/queued'
            out.mkdir(parents=True)
            ns['jobs']['queued'] = dict(id='queued', status='queued', files=[])
            ns['save_job'](ns['jobs']['queued'])
            self.assertEqual(ns['stop_job']('queued')['status'], 'stopped')
            ns['clear_job']('queued')
            self.assertEqual(ns['list_jobs'](), [])
            ns['jobs'].clear()
            record = dict(id='queued', status='running', files=[])
            ns['save_job'](record)
            self.assertEqual(ns['get_job']('queued')['status'], 'interrupted')
            ns['clear_job']('queued')
            self.assertEqual(ns['list_jobs'](), [])
            with self.assertRaises(ApiError):
                ns['clear_job']('../outside')


if __name__ == '__main__':
    unittest.main()
