import subprocess
import io
import os
import json
import unittest
import uuid
from pathlib import Path
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('CK2_TEST_URL', 'http://127.0.0.1:7888')

class SessionTests(unittest.TestCase):
    def test_session_assets_and_missing_files(self):
        p = requests.post(BASE+'/api/projects', json={'name':'Persistence verification'}).json()
        pid = p['id']
        clip = ROOT/'inputs'/f'{uuid.uuid4().hex}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=green:s=320x240:r=24:d=0.2', '-c:v', 'libx264', str(clip)], check=True)
        asset = None
        image_asset = None
        output = ROOT/'outputs'/uuid.uuid4().hex
        output.mkdir()
        try:
            with clip.open('rb') as f:
                r = requests.post(BASE+'/api/assets', files={'video':(clip.name,f,'video/mp4')})
            self.assertEqual(r.status_code,200,r.text)
            asset=r.json()
            png = io.BytesIO()
            Image.new('L', (320, 240), 255).save(png, format='PNG')
            image_response = requests.post(BASE+'/api/hint-images', files={'image':('mask.png',png.getvalue(),'image/png')})
            self.assertEqual(image_response.status_code, 200, image_response.text)
            image_asset = image_response.json()
            self.assertEqual(requests.get(BASE+'/api/assets/'+image_asset['id']).headers['content-type'], 'image/png')
            state={'sourceAsset':asset,'hintAsset':asset,'hintImageAsset':image_asset,'hintFrame':4,
                   'quality':.72,'carry':False,'logs':{'job':True},'media':{'sample':{'time':3.5}}}
            r=requests.put(BASE+'/api/ui-state',params={'project_id':pid},json=state)
            self.assertEqual(r.status_code,200)
            restored=requests.get(BASE+'/api/ui-state',params={'project_id':pid}).json()
            for key,value in state.items(): self.assertEqual(restored[key],value)
            png_path = ROOT/'inputs'/image_asset['id']/'hint.png'
            offline_png = png_path.with_suffix('.offline')
            png_path.rename(offline_png)
            try:
                missing_png = requests.get(BASE+'/api/ui-state',params={'project_id':pid}).json()
                self.assertNotIn('hintImageAsset', missing_png)
                self.assertEqual(missing_png['hintFrame'], 4)
            finally:
                offline_png.rename(png_path)
            self.assertEqual(requests.get(BASE+'/api/assets/'+asset['id'],headers={'Range':'bytes=0-9'}).status_code,206)
            path=next((ROOT/'inputs'/asset['id']).glob('*.mp4'))
            moved=path.with_suffix('.offline')
            path.rename(moved)
            try:
                missing=requests.get(BASE+'/api/ui-state',params={'project_id':pid}).json()
                self.assertNotIn('sourceAsset',missing)
                self.assertNotIn('hintAsset',missing)
            finally: moved.rename(path)
            job={'id':output.name,'name':'Test','project_id':pid,'status':'complete','files':['missing.mp4'],'metadata':{}}
            (output/'job.json').write_text(json.dumps(job),encoding='utf-8')
            history=requests.get(BASE+'/api/jobs',params={'project_id':pid}).json()
            self.assertEqual(len(history),1)
            self.assertEqual(history[0]['files'],[])
            self.assertNotIn(output.name,[j['id'] for j in requests.get(BASE+'/api/jobs').json()])
            self.assertEqual(requests.patch(BASE+'/api/projects/'+pid,json={'name':'Renamed project'}).status_code,200)
            self.assertIn('Renamed project',[p['name'] for p in requests.get(BASE+'/api/projects').json()])
        finally:
            clip.unlink(missing_ok=True)
            (ROOT/'projects'/f'{pid}.json').unlink(missing_ok=True)
            (output/'job.json').unlink(missing_ok=True)
            output.rmdir()
            if asset:
                folder=ROOT/'inputs'/asset['id']
                for path in folder.iterdir(): path.unlink()
                folder.rmdir()
            if image_asset:
                folder=ROOT/'inputs'/image_asset['id']
                for path in folder.iterdir(): path.unlink()
                folder.rmdir()

if __name__=='__main__':unittest.main()
