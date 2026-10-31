"""Shared upstream memory estimates; importing this module does not load torch."""

# Peak GPU memory in GiB by megapixels of model input, measured at each Hann
# chunk size. Keys are low_vram False/True.
_VRAM_PEAK_GB = {
    False: ((8, 24, 48, 80), (
        (0.98, (6.19, 7.52, 9.77, 12.89)),
        (2.21, (7.50, 11.33, 18.66, 24.89)),
        (3.93, (9.06, 14.78, 23.92, 33.19)),
        (8.36, (13.94, 25.96, 45.15, 70.45)),
    )),
    True: ((1, 2, 4, 8, 24, 48, 80), (
        (0.98, (2.71, 2.78, 2.94, 3.25, 4.54, 6.57, 9.50)),
        (2.21, (2.80, 2.97, 3.35, 4.12, 7.69, 13.20, 20.56)),
        (3.93, (2.92, 3.23, 3.85, 5.09, 10.09, 17.57, 27.75)),
        (8.36, (3.25, 3.92, 5.28, 8.38, 20.78, 39.66, 64.65)),
    )),
}
_VRAM_MARGIN_SCALE = 1.1
_VRAM_MARGIN_GB = 0.3


def _interp(x: float, points) -> float:
    """Piecewise-linear through (x, y) points, extrapolating past the ends."""
    points = list(points)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1 or (x1, y1) == points[-1]:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[0][1]


def estimate_peak_vram_gb(megapixels: float, frames: int, low_vram: bool) -> float:
    """Estimated peak GPU memory for a Hann window of `frames` frames."""
    chunks, rows = _VRAM_PEAK_GB[low_vram]
    frames = max(frames, chunks[0])
    per_chunk = [
        max(_interp(megapixels, [(mp, peaks[i]) for mp, peaks in rows]), rows[0][1][i])
        for i in range(len(chunks))
    ]
    return _interp(frames, zip(chunks, per_chunk))
