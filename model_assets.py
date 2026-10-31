"""Fetch missing inference assets before launching the offline GPU process."""
import os
from pathlib import Path
import subprocess
import sys
from engine.model_variants import get_variant


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


def required_files(variant='fp32'):
    selected = get_variant(variant)
    return ('weights/'+selected['filename'],)+REQUIRED_FILES[1:]


def models_ready(root, variant='fp32'):
    models = Path(root) / 'models'
    return all((models / name).is_file() and (models / name).stat().st_size > 0
               for name in required_files(variant))


def ensure_models(root, log, runner=None, variant='fp32'):
    root = Path(root).resolve()
    get_variant(variant)
    if models_ready(root, variant):
        return
    print('Downloading missing inference models into models/. This can take several minutes.',
          file=log, flush=True)
    env = dict(os.environ, PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='0',
               TRANSFORMERS_OFFLINE='0', HF_HOME=str(root / '.cache' / 'huggingface'))
    cmd = [sys.executable, '-u', str(root / 'engine/scripts/download_weights.py')]
    if variant != 'fp32':
        cmd.extend(['--model_variant', variant])
    cmd.extend(['--package_root', str(root / 'models')])
    (runner or subprocess.run)(
        cmd,
        cwd=root, stdout=log, stderr=subprocess.STDOUT, env=env, check=True,
    )
    if not models_ready(root, variant):
        raise RuntimeError('Model download incomplete. Check the processing log and retry the job.')
    print('Models ready. Starting inference.', file=log, flush=True)
