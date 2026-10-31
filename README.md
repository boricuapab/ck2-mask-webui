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

| Asset | Download source | Local destination |
| --- | --- | --- |
| CorridorKey 2.0 and foundation statistics | [CorridorKey on Hugging Face](https://huggingface.co/nikopueringer/CorridorKey2.0) | `models/weights/` |
| C-RADIOv4-SO400M | [NVIDIA](https://huggingface.co/nvidia/C-RADIOv4-SO400M) | `models/vfms/cradio/C-RADIOv4-SO400M/` |
| MoGe-2 ViT-B | [MoGe weights](https://huggingface.co/Ruicheng/moge-2-vitb-normal) | `models/vfms/moge/` |
| RVM small | [Google DeepMind](https://github.com/google-deepmind/representations4d) | `models/vfms/rvm/` |

Foundation-model revisions are pinned by the upstream download script; RVM also has a checksum check. The C-RADIO download includes the code and configuration needed to load its weights locally. Subsequent jobs reuse local assets and run inference with offline model loading. If a download fails, inspect the log, restore connectivity or free disk space, and submit the job again; the downloader reuses cached files.

To download the models ahead of time:

```powershell
uv run --locked --no-sync python engine/scripts/download_weights.py --package_root models
```

## Use the interface

1. Create or select a **Project session**. Sessions save settings, selected footage, render history, and playback positions.
2. Upload a source video or select one from the local clip library. To populate the library manually, place clips in `inputs/`.
3. Optionally convert to 720p, 1080p, or 4K at 24, 30, 48, 60, 96, or 120 fps. Conversion preserves duration and aspect ratio with padding; it drops or duplicates frames without motion interpolation. Click **Use converted footage** afterward.
4. Optionally attach a hint-mask video: white keeps the subject; black removes the background. Match source dimensions, frame rate, duration, and frame alignment. Paired source/hint conversion is available.
5. Choose **Inference length**: **Full shot** (default), **Frame count** with a positive whole number, or **Seconds** with a positive duration. Limited runs start at the beginning. Seconds use the selected source's frame rate, rounded up to a whole frame; requests longer than the shot stop at its end. These settings are saved per project, and each render records its selected length in the result card and processing log. Adjust hint confidence and temporal hint carry, then click **Process on GPU**. Jobs run one at a time and show temporal-window progress and processing logs. Completed renders show elapsed inference time in the result card and processing log, including model loading and output writing but excluding queue wait and model downloads. Timing is saved with render history; older renders without recorded timing keep their existing display.
6. Preview and download completed results. Use **Stop run** to cancel queued work, model downloads, or active inference; stopping also terminates child encoders and releases the queue for the next job. Once a run has stopped or finished, use **Clear from UI** to hide it from project render history. Clearing stays in effect after restarting the app and keeps files on disk. Partial outputs from stopped runs are not shown.

Each render produces an alpha-matte MP4, foreground MP4, checkerboard-preview MP4, and transparent ProRes 4444 MOV. Use the MOV for compositing; browser playback may not display its transparency. **Inference outputs omit source audio.** Footage conversion preserves audio as AAC when present.

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
