"""Translate the user's processing length into the engine's frame limit."""
import math
from decimal import Decimal


def resolve_length(mode, frame_count, seconds, fps):
    if mode == 'full':
        return dict(mode='full', num_frames=-1, label='Full shot')
    if mode == 'frames':
        try:
            frames = int(frame_count)
        except (ValueError, TypeError, OverflowError):
            raise ValueError('Frame count must be a positive whole number.') from None
        if frames <= 0:
            raise ValueError('Frame count must be a positive whole number.')
        return dict(mode=mode, num_frames=frames, label=f'First {frames} frames')
    if mode == 'seconds':
        try:
            duration = float(seconds)
            rate = float(fps)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError()
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError()
            frames = max(1, math.ceil(Decimal(str(duration)) * Decimal(str(rate))))
        except (ValueError, TypeError, OverflowError):
            raise ValueError('Duration must be a positive number of seconds with a valid source frame rate.') from None
        return dict(mode=mode, seconds=duration, num_frames=frames,
                    label=f'First {duration:g}s ({frames} frames at {rate:g} fps)')
    raise ValueError('Choose full shot, frame count, or seconds.')
