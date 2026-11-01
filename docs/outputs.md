# Output files

[Feature index](README.md)

Each completed render produces:

| File | Use |
| --- | --- |
| Alpha-matte MP4 | Inspect or reuse the predicted matte. |
| Foreground MP4 | Inspect the raw predicted foreground, without additional despill. |
| Checkerboard-preview MP4 | Review the keyed result with the selected despill and [comparison wipe](comparison-wipe.md). |
| Transparent ProRes 4444 MOV | Composite the cutout using its alpha channel and selected despill. |

Use the MOV for compositing; browser players may not display its transparency. **Inference outputs omit source audio.** [Footage conversion](conversion.md) preserves audio as AAC when present.

Native output resolution is preserved. The model may pad dimensions internally for inference, then crops that padding away when writing results.

Download files from their render card. Results, settings, and logs are stored under `outputs/<job-id>/`; see [Local files](../README.md#local-files). Clearing a render from the UI keeps these files on disk.
