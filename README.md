# CorridorKey Mask WebUI

A local browser interface for **CorridorKey 2.0** video matting. Upload footage, optionally attach a hint-mask video, convert clips, and render alpha mattes and transparent cutouts on your NVIDIA GPU.

This project is based on [nikopueringer/CorridorKey2.0](https://github.com/nikopueringer/CorridorKey2.0). The CorridorKey model was designed and trained by Zachary Harris in collaboration with Niko and Corridor Digital. This repository adds a FastAPI web interface, persistent project sessions, footage conversion, a sequential GPU render queue, and automatic model downloads. It is an independent community interface.

## Requirements

- Windows x64. The included dependency lock targets this platform.
- An NVIDIA GPU supported by CUDA 13.0 PyTorch and a compatible NVIDIA driver. Upstream lists RTX 30-series or newer, with at least 4 GB VRAM for footage up to 1440p or 6 GB for 4K; longer clips and larger temporal windows may require more memory.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) on PATH. uv manages the Python 3.12 environment and can download Python automatically.
- [Git](https://git-scm.com/downloads) on PATH, including for the pinned utils3d dependency.
- [FFmpeg and FFprobe](https://ffmpeg.org/download.html) on PATH, with H.264, AAC, and ProRes encoding support.
- Internet access for installation and the first inference model download. Allow several gigabytes for models, plus dependencies, footage, and rendered outputs.

## Install and launch

```powershell
git clone https://github.com/boricuapab/ck2-mask-webui.git
cd ck2-mask-webui
.\setup.bat
.\launch.bat
```

Open **http://127.0.0.1:7888** once the server starts. The server binds to localhost. The hardware badge reports your GPU, VRAM, and system RAM. GPU processing is disabled when CUDA is unavailable.

Equivalent terminal commands after cloning:

```powershell
uv sync --locked
uv run --locked --no-sync app.py
```

The default environment uses the checked-in `uv.lock`: Python 3.12, PyTorch 2.13.0 with CUDA 13.0, torchvision 0.28.0, NumPy 2.5.2, and OpenCV 4.14.0.94. No bundled Python installation, virtual environment, or tool executable is required.

## First inference and model downloads

The environment includes `hf-xet` for accelerated downloads from Hugging Face Xet storage. Existing installations can run `uv sync --locked` after updating, then restart the app to use it.

Model weights are **not included in this repository**. Submit a clip with **Process on GPU** to download missing assets automatically before inference. The job displays a download status; expand **Processing log** for details. The first job may take several minutes before GPU processing begins.

Use **Inference model** to choose **FP32** (the default original checkpoint) or **INT8 ConvRot**, converted by boricuapab. The choice is saved per project and captured when each job is submitted, so changing the dropdown does not change queued jobs. Only the selected main checkpoint is required or downloaded; both variants share foundation statistics and the three foundation models. Each render shows its model in the result card and processing log. Existing projects and API requests default to FP32. The FP32 label describes checkpoint storage; the engine retains its existing mixed-precision inference behavior.

| Asset | Download source | Local destination |
| --- | --- | --- |
| CorridorKey 2.0 and foundation statistics | [CorridorKey on Hugging Face](https://huggingface.co/nikopueringer/CorridorKey2.0) | `models/weights/` |
| Optional INT8 ConvRot checkpoint | [boricuapab's converted model](https://huggingface.co/boricuapab/corridorkey_v2_int8_convrot) | `models/weights/corridorkey_v2_int8_convrot.safetensors` |
| C-RADIOv4-SO400M | [NVIDIA](https://huggingface.co/nvidia/C-RADIOv4-SO400M) | `models/vfms/cradio/C-RADIOv4-SO400M/` |
| MoGe-2 ViT-B | [MoGe weights](https://huggingface.co/Ruicheng/moge-2-vitb-normal) | `models/vfms/moge/` |
| RVM small | [Google DeepMind](https://github.com/google-deepmind/representations4d) | `models/vfms/rvm/` |

Foundation-model revisions are pinned by the upstream download script; RVM also has a checksum check. The C-RADIO download includes the code and configuration needed to load its weights locally. Subsequent jobs reuse local assets and run inference with offline model loading. If a download fails, inspect the log, restore connectivity or free disk space, and submit the job again; the downloader reuses cached files.

To download the models ahead of time:

```powershell
uv run --locked --no-sync python engine/scripts/download_weights.py --package_root models
```

To download the INT8 variant instead:

```powershell
uv run --locked --no-sync python engine/scripts/download_weights.py --model_variant int8_convrot --package_root models
```

The INT8 checkpoint revision is pinned in `engine/model_variants.py`. Its 167 quantized linear layers keep INT8 weights, apply the matching regular-Hadamard ConvRot transform, dynamically quantize activations, and use INT8 CUDA matrix multiplication. The loader implements the [Comfy Quants W8A8 checkpoint format](https://github.com/Comfy-Org/comfy-quants/blob/main/docs/formats/int8_w8a8.md); ComfyUI is not required. Quantization can change output quality and performance. Chunk suggestions retain the conservative FP32 memory estimates for both variants rather than assuming that all inference memory scales with checkpoint size.

## Documentation

Start with [Use the interface](docs/README.md), or jump to a feature:

| Feature | Guide |
| --- | --- |
| Project sessions | [Create, switch, and restore projects](docs/projects.md) |
| Source footage | [Uploads and the clip library](docs/footage.md) |
| Footage conversion | [Resolution and frame rate](docs/conversion.md) |
| Video hints | [Hint videos, confidence, and carry](docs/video-hints.md) |
| PNG hints | [Single-frame hints at any selected frame](docs/png-hints.md) |
| Model selection | [FP32 and INT8 ConvRot](docs/models.md) |
| Inference length | [Full shot, frames, or seconds](docs/inference-length.md) |
| Temporal chunks | [GPU suggestions and manual chunk sizes](docs/temporal-chunks.md) |
| Despill | [Green suppression and color preservation](docs/despill.md) |
| Render queue | [Progress, timing, stop, and clear](docs/render-queue.md) |
| Comparison wipe | [Synchronized input/keyed playback](docs/comparison-wipe.md) |
| Output files | [Mattes, previews, and transparent exports](docs/outputs.md) |

## Local files

All application data paths are relative to the checkout:

| Folder | Contents |
| --- | --- |
| `inputs/` | Uploaded sources, hint masks, and library clips |
| `inputs/converted/` | Converted footage and hints |
| `models/` | Automatically downloaded inference assets |
| `outputs/<job-id>/` | Rendered videos, settings, and logs |
| `projects/` | Saved project sessions |
| `conversions/` | Conversion history |
| `.cache/` | Model download cache |

These folders are created as needed and ignored by Git. No personal footage, generated outputs, saved sessions, model weights, or machine-specific paths are shipped. Back up the data folders together to preserve sessions and their referenced media. Restarting preserves completed work; interrupted jobs must be resubmitted.

## Upstream code and license

The inference engine and its notices are retained in `engine/`, including the vendored MoGe code and its license. Changes include model paths under `models/` and grouped-attention dtype compatibility under PyTorch autocast. The web interface and automatic first-inference download integration are additions in this repository.

This derivative is distributed under the **Corridor Key Licence**, reproduced in [LICENSE](LICENSE) and [engine/LICENSE](engine/LICENSE). Read the complete license and its additional terms before use or redistribution. Third-party components retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [MoGe's license](engine/third_party/MoGe/LICENSE).

Original project: **[CorridorKey 2.0 by Corridor Digital](https://github.com/nikopueringer/CorridorKey2.0)**.

## Development checks

After installing the environment, run the model-download and CUDA attention tests:

```powershell
uv run --locked --no-sync python -m unittest discover -s tests -p test_model_download.py -v
uv run --locked --no-sync python -m unittest discover -s tests -p test_attention_dtype.py -v
```

The download tests mock network requests. The attention regression test requires CUDA and is skipped when CUDA is unavailable.

To run the complete suite, start the app in one terminal:

```powershell
uv run --locked --no-sync app.py
```

Then run all tests in another terminal from the repository root:

```powershell
uv run --locked --no-sync python -m unittest discover -s tests -v
```

Session, conversion, and frame-rate integration tests require that running server and FFmpeg/FFprobe on PATH. They create synthetic footage and clean up their test assets. By default they connect to `http://127.0.0.1:7888`. To test an instance on a different port, set `CK2_TEST_URL` before running the suite:

```powershell
$env:CK2_TEST_URL = 'http://127.0.0.1:17888'
uv run --locked --no-sync python -m unittest discover -s tests -v
```
