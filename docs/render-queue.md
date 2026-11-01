# Render queue and controls

[Feature index](README.md)

After choosing footage and settings, click **Process on GPU**. Inference jobs run one at a time. Missing [model assets](models.md) download before inference starts.

The queue shows job status and temporal-window progress. Expand **Processing log** for download details, selected settings, and engine output. Window progress updates after each window completes, so a large chunk can take time before the next update.

Completed renders show elapsed inference time in the result card and log. This includes model loading and output writing, excluding queue wait and model downloads. Timing is saved with history; older jobs without recorded timing keep their existing display.

- **Stop run** cancels queued work, model downloads, or active inference. It also terminates child encoders and releases the queue for the next job. Partial outputs from stopped runs are not shown.
- **Clear from UI** becomes available after a run stops or finishes. It hides that run from project history, including after a restart, while keeping its files on disk.

Restarting preserves completed results; interrupted jobs must be submitted again. Inspect completed work with the [comparison wipe](comparison-wipe.md), then download the [output files](outputs.md).
