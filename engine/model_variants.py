"""Download locations for the two supported CorridorKey runtime checkpoints."""
MODEL_VARIANTS = {
    'fp32': dict(label='FP32 (default)', repo='nikopueringer/CorridorKey2.0',
                 filename='corridorkey_v2.safetensors', revision=None),
    'int8_convrot': dict(label='INT8 ConvRot', repo='boricuapab/corridorkey_v2_int8_convrot',
                        filename='corridorkey_v2_int8_convrot.safetensors',
                        revision='157e9ef2535acba7e058168d115aa97c9043a05a'),
}


def get_variant(name):
    if name not in MODEL_VARIANTS:
        raise ValueError('Choose FP32 or INT8 ConvRot.')
    return MODEL_VARIANTS[name]
