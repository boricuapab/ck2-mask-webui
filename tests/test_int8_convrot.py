import json
from pathlib import Path
import sys
import unittest

import torch
from torch import nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
from corridorkey.int8_convrot import convrot, install_int8_linears


class Int8ConvRotTests(unittest.TestCase):
    def checkpoint(self):
        torch.manual_seed(12)
        model = nn.Sequential(nn.Linear(256, 128))
        weight = model[0].weight.detach().clone()
        rotated = convrot(weight)
        scale = (rotated.abs().amax(-1, keepdim=True)/127).clamp_min(1e-30)
        state = {'0.weight': (rotated/scale).round().clamp(-128, 127).to(torch.int8),
                 '0.weight_scale': scale, '0.bias': model[0].bias.detach().clone(),
                 '0.comfy_quant': torch.tensor(list(json.dumps(dict(convrot=True, convrot_groupsize=256,
                                                                     per_row=True)).encode()), dtype=torch.uint8)}
        return model, state, weight

    def test_rotation_matches_regular_hadamard_and_is_its_own_inverse(self):
        h4 = torch.tensor([[1, 1, 1, -1], [1, 1, -1, 1],
                           [1, -1, 1, 1], [-1, 1, 1, 1]], dtype=torch.float32)*.5
        h = torch.kron(torch.kron(torch.kron(h4, h4), h4), h4)
        x = torch.randn(3, 512)
        torch.testing.assert_close(convrot(x).reshape(-1, 256), x.reshape(-1, 256)@h.t())
        torch.testing.assert_close(convrot(convrot(x)), x, atol=1e-6, rtol=1e-5)

    def check_linear(self, device):
        model, state, weight = self.checkpoint()
        bias = state['0.bias'].clone()
        count = install_int8_linears(model, state, dict(format='int8_w8a8', quantized_linears=1))
        self.assertEqual(count, 1)
        model.load_state_dict(state, strict=True)
        model = model.to(device)
        self.assertEqual(model[0].weight.dtype, torch.int8)
        x = torch.randn(2, 23, 256, device=device)
        with torch.inference_mode():
            reference = F.linear(x, weight.to(device), bias.to(device))
            actual = model(x)
        self.assertEqual(actual.shape, reference.shape)
        self.assertLess(((actual-reference).square().mean()/reference.square().mean()).sqrt().item(), .02)
        if device == 'cuda':
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                self.assertEqual(model(x).dtype, torch.bfloat16)

    def test_cpu_reference_and_int8_storage(self):
        self.check_linear('cpu')

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA INT8 kernel check')
    def test_cuda_int8_matmul_and_autocast(self):
        self.check_linear('cuda')

    def test_rejects_unsupported_metadata(self):
        model, state, _ = self.checkpoint()
        with self.assertRaises(ValueError):
            install_int8_linears(model, state, dict(format='unknown'))


if __name__ == '__main__':
    unittest.main()
