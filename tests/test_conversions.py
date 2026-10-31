import os
import hashlib
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get('CK2_TEST_URL', 'http://127.0.0.1:7888')

class ConversionTests(unittest.TestCase):
    def test_presets_hint_alignment_and_original(self):
        pid=requests.post(BASE+'/api/projects',json={'name':'Conversion verification'}).json()['id']
        assets=[];records=[]
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as temp:
                source=Path(temp)/'sample.mp4'
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=green:s=320x240:r=25:d=0.5','-f','lavfi','-i','sine=frequency=440:duration=0.5','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(source)],check=True)
                before=hashlib.sha256(source.read_bytes()).hexdigest()
                with source.open('rb') as f:
                    r=requests.post(BASE+'/api/assets',files={'video':('sample.mp4',f,'video/mp4')})
                r.raise_for_status();asset=r.json();assets.append(asset['id'])
                for resolution,size in [('720p',(1280,720)),('1080p',(1920,1080)),('2160p',(3840,2160))]:
                    data={'project_id':pid,'asset_id':asset['id'],'resolution':resolution,'name':'sample'}
                    if resolution=='720p':data['hint_id']=asset['id']
                    r=requests.post(BASE+'/api/conversions',json=data);r.raise_for_status();cid=r.json()['id'];records.append(cid)
                    deadline=time.monotonic()+90
                    while time.monotonic()<deadline:
                        record=next(x for x in requests.get(BASE+'/api/conversions',params={'project_id':pid}).json() if x['id']==cid)
                        if record['status'] in ('complete','failed'):break
                        time.sleep(.2)
                    self.assertEqual(record['status'],'complete',record)
                    self.assertEqual(record['progress'],100)
                    for kind,result in record['assets'].items():
                        assets.append(result['id'])
                        self.assertEqual((result['width'],result['height']),size)
                        self.assertEqual(result['fps'],24)
                        self.assertLess(abs(result['duration']-.52),.07)
                    if resolution=='720p':self.assertIn('hint',record['assets'])
                self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
                self.assertEqual(requests.post(BASE+'/api/conversions',json={'project_id':pid,'asset_id':asset['id'],'resolution':'invalid'}).status_code,400)
        finally:
            (ROOT/'projects'/f'{pid}.json').unlink(missing_ok=True)
            for cid in records:(ROOT/'conversions'/f'{cid}.json').unlink(missing_ok=True)
            for aid in assets:
                folder=next((f for f in (ROOT/'inputs'/aid,ROOT/'inputs'/'converted'/aid) if f.exists()),ROOT/'inputs'/aid)
                if folder.exists():
                    for p in folder.iterdir():p.unlink()
                    folder.rmdir()

if __name__=='__main__':unittest.main()
