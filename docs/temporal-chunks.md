# Temporal chunk size

[Feature index](README.md)

Use **Temporal chunk size** to control how many frames the model processes together. Smaller chunks use less GPU memory; larger chunks provide more temporal context.

**Automatic** is the default. Suggestions account for currently free GPU VRAM, padded input resolution, source length, and the selected [inference length](inference-length.md), with extra memory headroom. Automatic recalculates when each queued job starts, after previous jobs release the GPU.

Manual choices are **1, 2, 4, 8, 16, 24, 32, 48, 64, or 80 frames**. Overlap is approximately half the chunk size; one-frame chunks have no overlap. Short renders cap the actual chunk to the selected frame count.

Click **Refresh suggestion** to update the estimate or **Use suggested** to select it manually. Manual chunks also offer **Low-memory processing**. Actual chunk, stride, and low-memory settings appear in render history and logs.

For example, 720p footage with about 14.8 GiB free on a 16 GiB GPU suggests a 24-frame chunk. Other running GPU jobs reduce the memory currently available. Suggestions are estimates, not a guarantee that a workload will fit.
