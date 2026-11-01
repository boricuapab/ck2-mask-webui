# Footage conversion

[Feature index](README.md)

Select or upload footage, choose a resolution and output frame rate, then click **Convert selected footage**.

| Setting | Available values |
| --- | --- |
| Resolution | 720p (1280×720), 1080p (1920×1080), 4K UHD (3840×2160) |
| Frame rate | 24, 30, 48, 60, 96, or 120 fps |

Conversion creates a new H.264 MP4 and keeps the original. It preserves duration and aspect ratio with padding, dropping or duplicating frames without generating interpolated motion. Audio is preserved as AAC when present.

Enable **Convert attached hint mask too** to convert an aligned [hint video](video-hints.md) with the same settings. A source-only conversion clears an attached unconverted hint video when selected, avoiding an alignment mismatch.

Track progress under **Footage conversions**, then click **Use converted footage**. Click **Process on GPU** separately to key that copy.

Conversion does not resize [PNG hints](png-hints.md). Provide a PNG matching the selected source's dimensions if you change resolution.
