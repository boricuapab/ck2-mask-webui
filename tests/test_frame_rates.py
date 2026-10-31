import os
import time
import unittest
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('CK2_TEST_URL', 'http://127.0.0.1:7888')


class FrameRateTests(unittest.TestCase):
    def test_all_requested_rates_and_storage(self):
        project = requests.post(BASE+'/api/projects', json={'name': 'FPS verification'}).json()
        pid = project['id']
        fixture = ROOT/'tests'/'fps-fixture.mp4'
        assets, conversions = [], []
        try:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=green:s=320x240:r=25:d=0.2', '-c:v', 'libx264', str(fixture)], check=True)
            with fixture.open('rb') as f:
                response = requests.post(BASE+'/api/assets', files={'video': (fixture.name, f, 'video/mp4')})
            response.raise_for_status()
            source = response.json()
            assets.append(source['id'])
            self.assertTrue((ROOT/'inputs'/source['id']/fixture.name).is_file())
            for fps in (24, 30, 48, 60, 96, 120):
                response = requests.post(BASE+'/api/conversions', json={
                    'project_id': pid, 'asset_id': source['id'], 'resolution': '720p', 'fps': fps})
                response.raise_for_status()
                cid = response.json()['id']
                conversions.append(cid)
                deadline = time.monotonic()+60
                while time.monotonic() < deadline:
                    record = next(c for c in requests.get(BASE+'/api/conversions', params={'project_id': pid}).json() if c['id'] == cid)
                    if record['status'] in ('complete', 'failed'):
                        break
                    time.sleep(.1)
                self.assertEqual(record['status'], 'complete', record)
                asset = record['assets']['source']
                assets.append(asset['id'])
                self.assertEqual(asset['fps'], fps)
                path = ROOT/'inputs'/'converted'/asset['id']/asset['name']
                self.assertTrue(path.is_file())
                self.assertIn(f'_{fps}fps', path.name)
            response = requests.post(BASE+'/api/conversions', json={
                'project_id': pid, 'asset_id': source['id'], 'fps': 25})
            self.assertEqual(response.status_code, 400)
        finally:
            fixture.unlink(missing_ok=True)
            (ROOT/'projects'/f'{pid}.json').unlink(missing_ok=True)
            for cid in conversions:
                (ROOT/'conversions'/f'{cid}.json').unlink(missing_ok=True)
            for aid in assets:
                for folder in (ROOT/'inputs'/aid, ROOT/'inputs'/'converted'/aid):
                    if folder.exists():
                        for path in folder.iterdir():
                            path.unlink()
                        folder.rmdir()


if __name__ == '__main__':
    unittest.main()
