"""Frame-position validation and explicit single-image hint placement."""


def validate_hint_frame(frame_number, source_frames, requested_frames):
    count = source_frames if requested_frames <= 0 else min(source_frames, requested_frames)
    if not 1 <= frame_number <= count:
        raise ValueError(f'PNG hint frame must be between 1 and {count} in the selected inference range.')
    return frame_number-1


def inject_frame_hint(hints, quality, present, image, frame_index, start, end, confidence):
    if image is None or not start <= frame_index < end:
        return False
    position = frame_index-start
    # Explicit PNG always overrides an overlapping carried hint or hint-video frame.
    hints[0, position] = image.to(dtype=hints.dtype)
    quality[0, position] = float(confidence)
    present[0, position] = True
    return True
