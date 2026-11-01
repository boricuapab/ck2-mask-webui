# Use the interface

Open **http://127.0.0.1:7888** after launching the app. See the repository [README](../README.md) for installation, model downloads, and requirements.

## Feature guides

| Feature | Guide |
| --- | --- |
| Project sessions | [Create, switch, rename, and restore projects](projects.md) |
| Source footage | [Upload videos and use the local clip library](footage.md) |
| Footage conversion | [Change resolution and frame rate](conversion.md) |
| Video hints | [Use aligned hint-mask videos, confidence, and carry](video-hints.md) |
| PNG hints | [Anchor a single PNG matte at any selected frame](png-hints.md) |
| Model selection | [Choose FP32 or INT8 ConvRot](models.md) |
| Inference length | [Process the full shot, a frame count, or seconds](inference-length.md) |
| Temporal chunks | [Use GPU-based suggestions and manual chunk sizes](temporal-chunks.md) |
| Despill | [Control green suppression and preserve green subjects](despill.md) |
| Render queue | [Submit, monitor, stop, and clear runs](render-queue.md) |
| Comparison wipe | [Compare input and keyed video with synchronized playback](comparison-wipe.md) |
| Output files | [Choose the right preview, matte, or transparent export](outputs.md) |

## Typical workflow

1. Create or select a [project](projects.md), then [upload or select footage](footage.md).
2. Optionally [convert footage](conversion.md) and attach a [hint video](video-hints.md) or [PNG hint](png-hints.md).
3. Choose the [model](models.md), [inference length](inference-length.md), [chunk size](temporal-chunks.md), and [despill strength](despill.md).
4. Click **Process on GPU** and monitor the [render queue](render-queue.md).
5. Inspect the [comparison wipe](comparison-wipe.md), then download your [outputs](outputs.md).
