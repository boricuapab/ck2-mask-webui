"""Conservative temporal-window suggestions, using the engine's memory estimates."""
import math

from engine.vram_budget import estimate_peak_vram_gb

CHUNK_CHOICES = (1, 2, 4, 8, 16, 24, 32, 48, 64, 80)


def validate_chunk(value):
    if value == 'auto':
        return 'auto'
    try:
        chunk = int(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Choose Automatic or a listed chunk size.') from None
    if chunk not in CHUNK_CHOICES:
        raise ValueError('Choose Automatic or a listed chunk size.')
    return chunk


def suggest_chunk(info, length, available_gib, total_gib):
    width, height = int(info['width']), int(info['height'])
    fps, duration = float(info['fps']), float(info['duration'])
    if min(width, height, fps, duration) <= 0 or not all(map(math.isfinite, (fps, duration, available_gib, total_gib))):
        raise ValueError('Valid video dimensions, duration, frame rate, and GPU memory are required.')
    padded_width, padded_height = math.ceil(width/128)*128, math.ceil(height/128)*128
    source_frames = max(1, math.ceil(duration*fps))
    frames = min(source_frames, length['num_frames']) if length['num_frames'] > 0 else source_frames
    candidates = [chunk for chunk in CHUNK_CHOICES if chunk <= frames]
    megapixels = padded_width*padded_height/1e6
    budget = max(0, min(available_gib, total_gib))
    # Extra headroom beyond the upstream estimator, especially for Windows GPU memory spill.
    for low_vram in (False, True):
        for chunk in reversed(candidates):
            if not low_vram and chunk < 8:
                continue
            estimate = estimate_peak_vram_gb(megapixels, chunk, low_vram)
            required = estimate*1.5 + 2.5
            if required <= budget:
                return dict(chunk=chunk, stride=max(1, chunk//2), low_vram=low_vram,
                            estimated_peak_gib=round(estimate, 2), fits=True,
                            frames=frames, windows=1 if frames <= chunk else 1+math.ceil((frames-chunk)/max(1, chunk//2)),
                            padded_width=padded_width, padded_height=padded_height,
                            available_gib=round(budget, 1), total_gib=round(total_gib, 1))
    return dict(chunk=1, stride=1, low_vram=True, fits=False, frames=frames, windows=frames,
                estimated_peak_gib=round(estimate_peak_vram_gb(megapixels, 1, True), 2),
                padded_width=padded_width, padded_height=padded_height,
                available_gib=round(budget, 1), total_gib=round(total_gib, 1))


def apply_chunk(job, cmd, gpu):
    """Resolve Automatic immediately before inference, after earlier jobs release memory."""
    recommendation = suggest_chunk(job['metadata'], job.get('processing_length', {'num_frames': -1}),
                                   gpu['free_gib'], gpu['total_gib'])
    requested = validate_chunk(job.get('chunk_size', 'auto'))
    chunk = recommendation['chunk'] if requested == 'auto' else min(requested, recommendation['frames'])
    low_vram = recommendation['low_vram'] if requested == 'auto' else job.get('low_vram', False)
    stride = max(1, chunk//2)
    cmd.extend(['--hann_chunk', str(chunk), '--hann_stride', str(stride)])
    if low_vram:
        cmd.append('--low_vram')
    job['chunk_settings'] = dict(chunk=chunk, stride=stride, low_vram=low_vram,
                                 automatic=requested == 'auto', suggested=recommendation['chunk'])
    return recommendation
