# Single-frame PNG hints

[Feature index](README.md)

Use a PNG matte to guide inference at a specific frame without preparing a full hint video.

1. Select the source footage and upload a **Single-frame PNG hint** matching its dimensions.
2. Use a black/white matte (white = subject, black = background), or a PNG alpha channel.
3. Set **Hint frame number**. The first source frame is **1**. Alternatively, pause the source preview on the matching frame and click **Use preview frame**.
4. Adjust [hint confidence and carry](video-hints.md), then submit the render.

The selected frame must be inside the [inference length](inference-length.md). For example, a 48-frame render accepts hint frames 1–48.

The PNG is applied at that exact frame in every overlapping chunk containing it, overriding a carried hint or hint-video frame there. It guides that temporal context and later carry when enabled. Earlier completed chunks are not reprocessed.

The uploaded PNG and frame number persist per project and appear in render history and logs. Click **Clear PNG hint** to detach it.

If source resolution changes, upload a matching PNG; [video conversion](conversion.md) does not resize PNG hints.
