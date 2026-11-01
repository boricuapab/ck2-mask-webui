"""Resolve a render's original footage without exposing arbitrary filesystem paths."""
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}


def find_job_source(job, inputs):
    inputs = Path(inputs).resolve()
    relative = job.get('source_relative')
    if relative:
        path = (inputs/relative).resolve()
        return path if path.is_relative_to(inputs) and path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS else None
    # Older jobs did not record their source. Prefer that job's direct upload.
    jid = str(job.get('id', ''))
    if not jid.isalnum():
        return None
    direct = [p.resolve() for p in (inputs/jid).glob('source.*')
              if p.suffix.lower() in VIDEO_EXTENSIONS and p.resolve().is_relative_to(inputs)]
    if len(direct) == 1:
        return direct[0]
    name = job.get('name')
    if not isinstance(name, str) or Path(name).name != name:
        return None
    matches = [p.resolve() for p in inputs.rglob('*')
               if p.is_file() and p.name == name and p.suffix.lower() in VIDEO_EXTENSIONS
               and p.resolve().is_relative_to(inputs)]
    return matches[0] if len(matches) == 1 else None
