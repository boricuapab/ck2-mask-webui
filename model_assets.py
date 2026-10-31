"""Fetch missing inference assets before launching the offline GPU process."""
import os
from pathlib import Path
import subprocess
import sys


REQUIRED_FILES = (
    'weights/corridorkey_v2.safetensors',
    'weights/foundation_stats.safetensors',
    'vfms/moge/model.pt',
    'vfms/cradio/C-RADIOv4-SO400M/model.safetensors',
    'vfms/cradio/C-RADIOv4-SO400M/config.json',
    'vfms/cradio/C-RADIOv4-SO400M/hf_model.py',
    'vfms/rvm/pretrain_rvm_small16_256_204031069.npz',
) + tuple('vfms/cradio/C-RADIOv4-SO400M/' + name + '.py' for name in (
    'adaptor_attn', 'adaptor_base', 'adaptor_generic', 'adaptor_mlp',
    'adaptor_module_factory', 'adaptor_registry', 'cls_token', 'common',
    'dinov2_arch', 'dual_hybrid_vit', 'enable_cpe_support', 'enable_damp',
    'enable_spectral_reparam', 'eradio_model', 'extra_models', 'extra_timm_models',
    'feature_normalizer', 'forward_intermediates', 'input_conditioner',
    'open_clip_adaptor', 'radio_model', 'siglip2_adaptor', 'utils',
    'vit_patch_generator', 'vitdet',
))


def models_ready(root):
    models = Path(root) / 'models'
    return all((models / name).is_file() and (models / name).stat().st_size > 0
               for name in REQUIRED_FILES)


def ensure_models(root, log, runner=None):
    root = Path(root).resolve()
    if models_ready(root):
        return
    print('Downloading missing inference models into models/. This can take several minutes.',
          file=log, flush=True)
    env = dict(os.environ, PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='0',
               TRANSFORMERS_OFFLINE='0', HF_HOME=str(root / '.cache' / 'huggingface'))
    (runner or subprocess.run)(
        [sys.executable, '-u', str(root / 'engine/scripts/download_weights.py'),
         '--package_root', str(root / 'models')],
        cwd=root, stdout=log, stderr=subprocess.STDOUT, env=env, check=True,
    )
    if not models_ready(root):
        raise RuntimeError('Model download incomplete. Check the processing log and retry the job.')
    print('Models ready. Starting inference.', file=log, flush=True)
