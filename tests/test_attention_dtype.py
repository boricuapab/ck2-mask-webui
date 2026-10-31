"""Regress the PyTorch 2.13 autocast/indexed-write dtype mismatch."""
import sys
import unittest
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
from corridorkey.blocks import _sdpa_with_region_groups, _sdpa_with_region_ids


@unittest.skipUnless(torch.cuda.is_available(), 'CUDA regression test')
class AttentionDtypeTests(unittest.TestCase):
    def test_full_partial_and_padded_windows_under_autocast(self):
        torch.manual_seed(14)
        regions = torch.tensor([[0, 0, 0, 0], [0, 0, 1, 1], [-1, 0, 0, 0]], device='cuda')
        mask = (regions[:, None, :, None] == regions[:, None, None, :]) & (regions[:, None, :, None] >= 0)
        for dtype in (torch.float32, torch.bfloat16):
            with self.subTest(dtype=dtype):
                q, k, v = [torch.randn(3, 2, 4, 8, device='cuda', dtype=dtype) for _ in range(3)]
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    reference = F.scaled_dot_product_attention(q, k, v, attn_mask=mask).to(dtype)
                    by_ids = _sdpa_with_region_ids(q, k, v, regions)
                    by_groups = _sdpa_with_region_groups(q, k, v, 3, (0,), (
                        ((0, 1), (1,)), ((2, 3), (1,)), ((1, 2, 3), (2,))))
                self.assertEqual(by_ids.dtype, dtype)
                self.assertEqual(by_groups.dtype, dtype)
                torch.testing.assert_close(by_ids, reference, atol=.02, rtol=.02)
                torch.testing.assert_close(by_groups, reference, atol=.02, rtol=.02)


if __name__ == '__main__':
    unittest.main()
