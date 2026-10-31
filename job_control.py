"""Coordinate cancellation with subprocess startup and kill encoder children too."""
import subprocess
import threading

import psutil


class JobStopped(Exception):
    pass


class JobControl:
    def __init__(self):
        self.lock = threading.RLock()
        self._cancelled = set()
        self._processes = {}

    def check(self, jid):
        with self.lock:
            if jid in self._cancelled:
                raise JobStopped()

    def cancel(self, jid):
        with self.lock:
            self._cancelled.add(jid)
            process = self._processes.get(jid)
            if process is None:
                return
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
            except psutil.NoSuchProcess:
                return
            targets = children + [parent]
            for target in targets:
                try:
                    target.terminate()
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs(targets, timeout=3)
            for target in alive:
                try:
                    target.kill()
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs(alive, timeout=3)
            if alive:
                raise RuntimeError('Some render processes could not be stopped. Try Stop run again.')

    def run(self, jid, cmd, *, check=False, **kwargs):
        with self.lock:
            self.check(jid)
            process = subprocess.Popen(cmd, **kwargs)
            self._processes[jid] = process
        try:
            code = process.wait()
        finally:
            with self.lock:
                self._processes.pop(jid, None)
        self.check(jid)
        if check and code:
            raise subprocess.CalledProcessError(code, cmd)
        return subprocess.CompletedProcess(cmd, code)

    def forget(self, jid):
        with self.lock:
            self._cancelled.discard(jid)
