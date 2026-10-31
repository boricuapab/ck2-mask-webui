"""Loopback-only CorridorKey workstation. Run with the project venv."""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from model_assets import ensure_models, models_ready
from job_control import JobControl, JobStopped

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT/'inputs'
CONVERTED = INPUTS/'converted'
MODELS = ROOT/'models'
os.environ.setdefault('HF_HOME', str(ROOT / '.cache' / 'huggingface'))
os.environ['CORRIDORKEY_MODELS_DIR'] = str(MODELS)
for folder in ('inputs', 'inputs/converted', 'models', 'outputs', 'projects', 'conversions'):
    (ROOT / folder).mkdir(exist_ok=True)
app = FastAPI(title='CorridorKey Local')
jobs = {}
job_control = JobControl()
ACTIVE_JOB_STATUSES = {'queued', 'downloading', 'running', 'stopping'}
pending = queue.Queue()
EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}
state_lock = threading.Lock()
conversion_queue = queue.Queue()
conversions = {}
RESOLUTIONS = {'720p': (1280, 720), '1080p': (1920, 1080), '2160p': (3840, 2160)}
FRAME_RATES = (24, 30, 48, 60, 96, 120)

def write_conversion(record):
    path = ROOT/'conversions'/f"{record['id']}.json"
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(record), encoding='utf-8')
    temp.replace(path)

@app.post('/api/conversions')
def convert_footage(data: dict = Body(...)):
    project_id = str(data.get('project_id', 'default'))
    if not project_path(project_id).exists():
        raise HTTPException(404, 'Project not found')
    resolution = data.get('resolution', '1080p')
    if resolution not in RESOLUTIONS:
        raise HTTPException(400, 'Choose 720p, 1080p, or 2160p')
    fps = data.get('fps', 24)
    if type(fps) is not int or fps not in FRAME_RATES:
        raise HTTPException(400, 'Choose 24, 30, 48, 60, 96, or 120 fps')
    source = asset_path(data.get('asset_id')) if data.get('asset_id') else next(
        (p for p in library() if p.name == data.get('source')), None)
    if source is None:
        raise HTTPException(400, 'Select or upload footage to convert')
    hint = asset_path(data.get('hint_id')) if data.get('hint_id') else None
    if data.get('hint_id') and hint is None:
        raise HTTPException(400, 'Saved hint no longer exists')
    info = probe(source)
    if hint:
        hi = probe(hint)
        if any(info[k] != hi[k] for k in ('width', 'height', 'fps')) or abs(info['duration']-hi['duration']) > 1/info['fps']:
            raise HTTPException(400, 'Source and hint must be aligned before converting them together')
    cid = uuid.uuid4().hex
    name = Path(str(data.get('name') or source.name)).stem
    record = dict(id=cid, project_id=project_id, status='queued', progress=0,
                  resolution=resolution, fps=fps, name=name, created_at=time.time(), assets={}, error='')
    conversions[cid] = record
    write_conversion(record)
    conversion_queue.put((record, source, hint, info))
    return record

@app.get('/api/conversions')
def list_conversions(project_id: str = 'default'):
    records = []
    for path in (ROOT/'conversions').glob('*.json'):
        record = conversions.get(path.stem) or json.loads(path.read_text(encoding='utf-8'))
        if record['project_id'] != project_id:
            continue
        record = dict(record)
        if record['id'] not in conversions and record['status'] in ('running', 'queued'):
            record['status'] = 'interrupted'
        record['assets'] = {k:v for k,v in record['assets'].items() if asset_path(v['id']) is not None}
        records.append(record)
    return sorted(records, key=lambda r:r['created_at'], reverse=True)

def conversion_worker():
    while True:
        record, source, hint, info = conversion_queue.get()
        try:
            record['status'] = 'running'
            write_conversion(record)
            width, height = RESOLUTIONS[record['resolution']]
            inputs = [('source', source)] + ([('hint', hint)] if hint else [])
            for index, (kind, path) in enumerate(inputs):
                aid = uuid.uuid4().hex
                folder = CONVERTED/aid
                folder.mkdir(parents=True)
                fps = record.get('fps', 24)
                safe_name = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in record['name'])[:160]
                target = folder/f"{safe_name}_{record['resolution']}_{fps}fps{'_hint' if kind == 'hint' else ''}.mp4"
                temporary = folder/'encoding.mp4'
                filters = f'fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
                cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-i', str(path),
                       '-map', '0:v:0', '-map', '0:a?', '-vf', filters, '-c:v', 'libx264', '-threads', '2',
                       '-preset', 'medium', '-crf', '0' if kind == 'hint' else '16', '-pix_fmt', 'yuv420p',
                       '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-progress', 'pipe:1', str(temporary)]
                with (folder/'conversion.log').open('w', encoding='utf-8') as log:
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, text=True)
                    for line in process.stdout:
                        if line.startswith('out_time_us='):
                            try:
                                fraction = min(1, max(0, int(line.split('=')[1])/1e6/info['duration']))
                                record['progress'] = min(99, round(100*(index+fraction)/len(inputs)))
                            except ValueError:
                                pass
                    if process.wait() != 0:
                        raise RuntimeError((folder/'conversion.log').read_text(encoding='utf-8')[-2000:])
                temporary.replace(target)
                record['assets'][kind] = dict(id=aid, name=target.name, **probe(target))
            record.update(status='complete', progress=100)
        except Exception as exc:
            record.update(status='failed', error=str(exc))
        write_conversion(record)
        conversion_queue.task_done()

def project_path(project_id):
    if not project_id.isalnum():
        raise HTTPException(400, 'Invalid project ID')
    return ROOT/'projects'/f'{project_id}.json'

default_project = project_path('default')
if not default_project.exists():
    old_state = ROOT/'ui-state.json'
    default_project.write_text(json.dumps(dict(id='default', name='My first project', created_at=time.time(),
        state=json.loads(old_state.read_text(encoding='utf-8')) if old_state.exists() else {})), encoding='utf-8')

@app.get('/api/projects')
def list_projects():
    with state_lock:
        records = [json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'projects').glob('*.json')]
    return [dict(id=p['id'], name=p['name'], created_at=p['created_at'])
            for p in sorted(records, key=lambda p:p['created_at'])]

@app.post('/api/projects')
def new_project(data: dict = Body(...)):
    name = str(data.get('name', '')).strip()[:120]
    if not name:
        raise HTTPException(400, 'Enter a project name')
    project = dict(id=uuid.uuid4().hex, name=name, created_at=time.time(), state={})
    with state_lock:
        project_path(project['id']).write_text(json.dumps(project), encoding='utf-8')
    return project

@app.patch('/api/projects/{project_id}')
def rename_project(project_id: str, data: dict = Body(...)):
    name = str(data.get('name', '')).strip()[:120]
    path = project_path(project_id)
    if not name or not path.exists():
        raise HTTPException(400, 'Project and name required')
    with state_lock:
        project = json.loads(path.read_text(encoding='utf-8'))
        project['name'] = name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(project), encoding='utf-8')
        temp.replace(path)
    return project

def asset_path(asset_id):
    if not isinstance(asset_id, str) or not asset_id.isalnum():
        return None
    for folder in (INPUTS/asset_id, CONVERTED/asset_id):
        path = next((p for p in folder.glob('*') if p.suffix.lower() in EXTENSIONS and p.name != 'encoding.mp4'), None)
        if path:
            return path
    return None

@app.get('/api/ui-state')
def get_ui_state(project_id: str = 'default'):
    path = project_path(project_id)
    if not path.exists():
        raise HTTPException(404, 'Project not found')
    with state_lock:
        state = json.loads(path.read_text(encoding='utf-8')).get('state', {})
    for key in ('sourceAsset', 'hintAsset'):
        if state.get(key) and asset_path(state[key].get('id')) is None:
            state.pop(key, None)
    if state.get('source') not in {p.name for p in library()}:
        state['source'] = ''
    return state

@app.put('/api/ui-state')
def save_ui_state(state: dict = Body(...), project_id: str = 'default'):
    if len(json.dumps(state)) > 100000:
        raise HTTPException(400, 'UI state too large')
    with state_lock:
        path = project_path(project_id)
        if not path.exists():
            raise HTTPException(404, 'Project not found')
        project = json.loads(path.read_text(encoding='utf-8'))
        project['state'] = state
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(project), encoding='utf-8')
        temp.replace(path)
    return {'saved': True}

@app.post('/api/assets')
async def upload_asset(video: UploadFile = File(...)):
    aid = uuid.uuid4().hex
    folder = INPUTS/aid
    folder.mkdir(parents=True)
    name = Path(video.filename or 'video').name
    path = folder/name
    await save_upload(video, path)
    try:
        info = probe(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(400, 'Cannot decode this video.')
    return dict(id=aid, name=name, **info)

@app.get('/api/assets/{asset_id}')
def get_asset(asset_id: str):
    path = asset_path(asset_id)
    if path is None:
        raise HTTPException(404)
    return FileResponse(path)

def probe(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_frames:format=duration',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    data = json.loads(p.stdout)
    stream = data['streams'][0]
    a, b = map(int, stream['avg_frame_rate'].split('/'))
    return dict(width=stream['width'], height=stream['height'], fps=a/b,
                duration=float(data['format']['duration']))

def library():
    return sorted(p for folder in (INPUTS, CONVERTED) for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in EXTENSIONS)

@app.get('/api/library')
def list_library():
    return [dict(id=p.name, name=p.name, **probe(p)) for p in library()]

@app.get('/api/library/{name}')
def library_video(name: str):
    path = next((p for p in library() if p.name == name), None)
    if not path:
        raise HTTPException(404)
    return FileResponse(path)

@app.get('/api/system')
def system():
    import torch
    import psutil
    cuda = torch.cuda.is_available()
    return dict(cuda=cuda, gpu=torch.cuda.get_device_name(0) if cuda else 'CUDA unavailable',
        gpu_memory_gib=round(torch.cuda.get_device_properties(0).total_memory/2**30, 1) if cuda else None,
        system_ram_gib=round(psutil.virtual_memory().total/2**30, 1),
        ready=models_ready(ROOT))

async def save_upload(upload, target):
    if Path(upload.filename or '').suffix.lower() not in EXTENSIONS:
        raise HTTPException(400, 'Please upload a video file.')
    with target.open('wb') as f:
        while chunk := await upload.read(1024 * 1024):
            f.write(chunk)
    await upload.close()

@app.post('/api/jobs')
async def create_job(video: UploadFile | None = File(None), hint: UploadFile | None = File(None),
                     source: str = Form(''), quality: float = Form(.95), carry: bool = Form(True),
                     saved_source: str = Form(''), saved_hint: str = Form(''), project_id: str = Form('default')):
    if not project_path(project_id).exists():
        raise HTTPException(404, 'Project not found')
    if not 0 <= quality <= 1:
        raise HTTPException(400, 'Hint confidence must be between 0 and 1.')
    jid = uuid.uuid4().hex
    folder = INPUTS/jid
    folder.mkdir()
    if video and video.filename:
        path = folder / ('source' + Path(video.filename).suffix.lower())
        await save_upload(video, path)
        name = Path(video.filename).name
    elif saved_source:
        path = asset_path(saved_source)
        if path is None:
            raise HTTPException(400, 'Saved source no longer exists. Upload it again.')
        name = get_ui_state(project_id).get('sourceAsset', {}).get('name', path.name)
    else:
        path = next((p for p in library() if p.name == source), None)
        if path is None:
            raise HTTPException(400, 'Select a library clip or upload a video.')
        name = path.name
    try:
        info = probe(path)
    except Exception:
        raise HTTPException(400, 'Cannot decode the source video.')
    hint_path = None
    if saved_hint:
        hint_path = asset_path(saved_hint)
        if hint_path is None:
            raise HTTPException(400, 'Saved hint no longer exists. Upload it again.')
    elif hint and hint.filename:
        hint_path = folder / ('hint' + Path(hint.filename).suffix.lower())
        await save_upload(hint, hint_path)
    if hint_path:
        try:
            hi = probe(hint_path)
        except Exception:
            raise HTTPException(400, 'Cannot decode the hint video.')
        if (info['width'], info['height']) != (hi['width'], hi['height']) or abs(info['fps']-hi['fps']) > .01 or abs(info['duration']-hi['duration']) > 1/info['fps']:
            raise HTTPException(400, 'Hint must match source dimensions, frame rate, and duration (within one frame).')
    out = ROOT/'outputs'/jid
    out.mkdir()
    cmd = [sys.executable, '-u', str(ROOT/'engine/infer.py'), '--input', str(path),
           '--output_dir', str(out), '--outputs', 'alpha', 'fg', 'checker', 'cutout',
           '--pix_fmt', 'yuv420p', '--hint_quality', str(quality)]
    if hint_path:
        cmd += ['--hint_video', str(hint_path)]
    if not carry:
        cmd += ['--no_carry_hint']
    jobs[jid] = dict(id=jid, name=name, status='queued', files=[], metadata=info, hinted=bool(hint_path),
                     project_id=project_id, created_at=time.time())
    (out/'job.json').write_text(json.dumps(jobs[jid]), encoding='utf-8')
    pending.put((jid, cmd, out))
    return jobs[jid]

def save_job(job):
    # Callers hold job_control.lock so clearing and finalization cannot overwrite each other.
    path = ROOT/'outputs'/job['id']/'job.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(job), encoding='utf-8')
    temporary.replace(path)


def get_job(jid):
    if not jid.isalnum():
        raise HTTPException(404, 'Render not found')
    if jid in jobs:
        return jobs[jid]
    path = ROOT/'outputs'/jid/'job.json'
    if not path.is_file():
        raise HTTPException(404, 'Render not found')
    job = json.loads(path.read_text(encoding='utf-8'))
    if job['status'] in ACTIVE_JOB_STATUSES:
        job['status'] = 'interrupted'
    return job


@app.post('/api/jobs/{jid}/stop')
def stop_job(jid: str):
    with job_control.lock:
        job = get_job(jid)
        if job['status'] not in ACTIVE_JOB_STATUSES:
            return {'status': job['status']}
        queued = job['status'] == 'queued'
        job['status'] = 'stopped' if queued else 'stopping'
        save_job(job)
        try:
            job_control.cancel(jid)
        except (OSError, RuntimeError) as exc:
            raise HTTPException(500, str(exc))
        return {'status': job['status']}


@app.post('/api/jobs/{jid}/clear')
def clear_job(jid: str):
    with job_control.lock:
        job = get_job(jid)
        if job['status'] in ACTIVE_JOB_STATUSES:
            raise HTTPException(409, 'Stop this run before clearing it from the UI.')
        job['hidden'] = True
        save_job(job)
        return {'status': 'cleared'}


def worker():
    while True:
        jid, cmd, out = pending.get()
        job = jobs[jid]
        try:
            with job_control.lock:
                job_control.check(jid)
                job['status'] = 'running'
            env = dict(os.environ, PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            with (out/'inference.log').open('w', encoding='utf-8') as log:
                if not models_ready(ROOT):
                    with job_control.lock:
                        job_control.check(jid)
                        job['status'] = 'downloading'
                    ensure_models(ROOT, log, runner=lambda cmd, **kwargs: job_control.run(jid, cmd, **kwargs))
                with job_control.lock:
                    job_control.check(jid)
                    job['status'] = 'running'
                inference_started = time.perf_counter()
                try:
                    code = job_control.run(jid, cmd, cwd=ROOT/'engine', stdout=log,
                                           stderr=subprocess.STDOUT, env=env).returncode
                finally:
                    job['inference_seconds'] = round(time.perf_counter() - inference_started, 2)
                outcome = 'completed' if code == 0 else 'failed'
                print(f"\nInference {outcome} in {job['inference_seconds']:.2f} seconds (excluding queue wait and model downloads).", file=log, flush=True)
            with job_control.lock:
                job_control.check(jid)
                job['status'] = 'complete' if code == 0 else 'failed'
                job['files'] = [p.name for p in out.iterdir() if p.suffix in {'.mp4', '.mov'}]
        except JobStopped:
            job.update(status='stopped', files=[])
            with (out/'inference.log').open('a', encoding='utf-8') as log:
                duration = f" after {job['inference_seconds']:.2f} seconds of inference" if 'inference_seconds' in job else ''
                print(f'\nRun stopped by user{duration}. Partial outputs are not shown.', file=log, flush=True)
        except Exception as e:
            job.update(status='failed', error=str(e))
        finally:
            with job_control.lock:
                save_job(job)
                job_control.forget(jid)
            pending.task_done()

@app.get('/api/jobs')
def list_jobs(project_id: str = 'default'):
    result = []
    for p in sorted((ROOT/'outputs').glob('*/job.json'), key=lambda p:p.stat().st_mtime, reverse=True):
        j = jobs.get(p.parent.name) or json.loads(p.read_text(encoding='utf-8'))
        if j.get('hidden') or j.get('project_id', 'default') != project_id:
            continue
        if j['id'] not in jobs and j['status'] in ACTIVE_JOB_STATUSES:
            j['status'] = 'interrupted'
        log = p.parent/'inference.log'
        j = dict(j, files=[f for f in j.get('files', []) if Path(f).name == f and (p.parent/f).is_file()],
                 log=log.read_text(encoding='utf-8', errors='replace')[-14000:] if log.exists() else '')
        result.append(j)
    return result

@app.get('/api/results/{jid}/{name}')
def result(jid: str, name: str):
    path = (ROOT/'outputs'/jid/name).resolve()
    if not path.is_relative_to(ROOT/'outputs') or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)

app.mount('/', StaticFiles(directory=ROOT/'web', html=True), name='web')
threading.Thread(target=worker, daemon=True).start()
threading.Thread(target=conversion_worker, daemon=True).start()
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=7888)
