# Model selection

[Feature index](README.md)

Use **Inference model** to select a checkpoint:

| Model | Behavior |
| --- | --- |
| FP32 — default | Uses the original CorridorKey checkpoint. Existing projects and API requests default to this option. |
| INT8 ConvRot | Uses boricuapab's converted checkpoint with quantized linear weights and dynamic INT8 activations. |

The choice is saved per project and captured when each job is submitted. Changing the dropdown does not change queued jobs. Each result card and processing log identifies its model.

Missing selected weights download automatically before inference. Only the selected main checkpoint is required; foundation statistics and the three foundation models are shared.

FP32 describes checkpoint storage; inference retains the engine's mixed-precision behavior. Quantization can change output quality and performance. [Chunk suggestions](temporal-chunks.md) use conservative FP32 memory estimates for both models.

See [First inference and model downloads](../README.md#first-inference-and-model-downloads) for sources, download commands, and INT8 format details.
