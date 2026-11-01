# Video hints, confidence, and carry

[Feature index](README.md)

Upload a video under **Optional hint-mask video** to guide subject selection throughout the shot. White keeps the subject; black removes the background.

The hint must match source dimensions, frame rate, duration, and frame alignment. Duration validation allows a difference of up to one source frame. Use [paired footage conversion](conversion.md) when preparing an aligned source and hint together.

**Hint confidence** controls how strongly the supplied hint guides inference; the default is 0.95. **Carry model hints between temporal windows** is enabled by default and lets overlapping windows reuse model predictions as continuing guidance.

Click **Clear hint** to detach the video. You can render without a hint, or use a [single-frame PNG hint](png-hints.md) instead. A PNG can also supplement the video, taking priority at its selected frame. Confidence and carry apply to PNG hints too.
