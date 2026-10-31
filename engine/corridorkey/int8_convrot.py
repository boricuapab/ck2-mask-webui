"""Comfy Quants W8A8 rowwise INT8 linears with regular-Hadamard ConvRot.

Format: https://github.com/Comfy-Org/comfy-quants/blob/main/docs/formats/int8_w8a8.md
Weights stay INT8. CUDA inference uses INT8 x INT8 -> INT32 matrix products.
"""
import json

import torch
from torch import nn
import torch.nn.functional as F


def convrot(x, group_size=256):
    """Normalized Kronecker powers of regular H4, not the Sylvester Hadamard."""
    original_shape = x.shape
    x = x.float().reshape(-1, group_size)
    step = 1
    while step < group_size:
        groups = x.reshape(-1, group_size // (4*step), 4, step)
        a, b, c, d = groups.unbind(-2)
        x = torch.stack((a+b+c-d, a+b-c+d, a-b+c+d, -a+b+c+d), -2)
        x = (x*.5).reshape(-1, group_size)
        step *= 4
    return x.reshape(original_shape)


class Int8ConvRotLinear(nn.Module):
    def __init__(self, linear, *, rotate, group_size):
        super().__init__()
        self.in_features, self.out_features = linear.in_features, linear.out_features
        self.rotate, self.group_size = rotate, group_size
        self.register_buffer('weight', torch.empty_like(linear.weight, dtype=torch.int8))
        self.register_buffer('weight_scale', torch.ones((self.out_features, 1), dtype=torch.float32,
                                                      device=linear.weight.device))
        self.register_buffer('bias', None if linear.bias is None else torch.zeros_like(linear.bias))

    def forward(self, x):
        shape = x.shape[:-1]+(self.out_features,)
        dtype = torch.get_autocast_dtype(x.device.type) if torch.is_autocast_enabled(x.device.type) else x.dtype
        flat = x.reshape(-1, self.in_features)
        output = torch.empty((flat.shape[0], self.out_features), device=x.device, dtype=dtype)
        # Bound rotation, quantization, and INT32 accumulator memory for long video windows.
        for start in range(0, flat.shape[0], 4096):
            part = flat[start:start+4096].float()
            if self.rotate:
                part = convrot(part, self.group_size)
            scale = (part.abs().amax(-1, keepdim=True)/127).clamp_min(1e-30)
            quantized = (part/scale).round().clamp(-128, 127).to(torch.int8)
            rows = quantized.shape[0]
            if x.is_cuda:
                padding = (-rows) % 32
                if padding:
                    quantized = F.pad(quantized, (0, 0, 0, padding))
                product = torch._int_mm(quantized.contiguous(), self.weight.t())[:rows]
            else:
                # CPU reference path for numerical tests; the web UI requires CUDA.
                product = quantized.int() @ self.weight.t().int()
            result = product.float()*scale*self.weight_scale.t()
            if self.bias is not None:
                result = result+self.bias.float()
            output[start:start+rows] = result.to(dtype)
        return output.reshape(shape)


def install_int8_linears(model, state_dict, metadata):
    if metadata.get('format') != 'int8_w8a8':
        raise ValueError('Unsupported quantized checkpoint format; expected int8_w8a8.')
    markers = [key for key in state_dict if key.endswith('.comfy_quant')]
    if not markers:
        raise ValueError('INT8 checkpoint has no per-layer quantization markers.')
    for key in markers:
        name = key.removesuffix('.comfy_quant')
        config = json.loads(bytes(state_dict[key].cpu().tolist()).decode('utf-8'))
        layer = model.get_submodule(name)
        weight, scale = state_dict[name+'.weight'], state_dict[name+'.weight_scale']
        if not isinstance(layer, nn.Linear) or weight.dtype != torch.int8 or tuple(weight.shape) != tuple(layer.weight.shape):
            raise ValueError(f'Invalid INT8 linear weight: {name}')
        if not config.get('per_row') or tuple(scale.shape) != (layer.out_features, 1):
            raise ValueError(f'Expected per-output-row scales: {name}')
        if not torch.isfinite(scale).all() or not (scale > 0).all():
            raise ValueError(f'Invalid INT8 scales: {name}')
        rotate = bool(config.get('convrot', False))
        group = int(config.get('convrot_groupsize', 256))
        if rotate and (group not in (4, 16, 64, 256, 1024) or layer.in_features % group):
            raise ValueError(f'Unsupported ConvRot group size for {name}: {group}')
        parent_name, _, child_name = name.rpartition('.')
        parent = model.get_submodule(parent_name) if parent_name else model
        setattr(parent, child_name, Int8ConvRotLinear(layer, rotate=rotate, group_size=group))
        del state_dict[key]
    expected = metadata.get('quantized_linears', len(markers))
    if expected != len(markers):
        raise ValueError(f'Expected {expected} INT8 linears, found {len(markers)}.')
    return len(markers)
