"""Stateless counter-based random numbers on int64 tensors.

Every random quantity in the simulator is a pure function of (hospital seed, stream id,
counter) where the counter is a tick index or a patient arrival ordinal. Nothing here keeps
state, so no draw can depend on the manager's actions: this is what gives common random
numbers. The mixer is the splitmix64 finaliser written with wrap-around int64 arithmetic and
logical shifts, which is bit-identical on CPU and CUDA.
"""
from __future__ import annotations

import torch


def _s64(x: int) -> int:
    x &= (1 << 64) - 1
    return x - (1 << 64) if x >= (1 << 63) else x


_C1 = _s64(0xBF58476D1CE4E5B9)
_C2 = _s64(0x94D049BB133111EB)
GOLD = _s64(0x9E3779B97F4A7C15)
_M30 = (1 << 34) - 1
_M27 = (1 << 37) - 1
_M31 = (1 << 33) - 1
_INV24 = 1.0 / float(1 << 24)


def mix(x: torch.Tensor) -> torch.Tensor:
    """splitmix64 finaliser. int64 in, int64 out."""
    x = (x ^ ((x >> 30) & _M30)) * _C1
    x = (x ^ ((x >> 27) & _M27)) * _C2
    return x ^ ((x >> 31) & _M31)


def key(base: torch.Tensor, stream: int, counter=0) -> torch.Tensor:
    """Derive a new key from `base` for (stream, counter). `counter` may be an int or tensor."""
    if isinstance(counter, int):
        return mix(base + _s64(stream * 0x632BE59BD9B4E019 + counter * GOLD))
    return mix(base + _s64(stream * 0x632BE59BD9B4E019) + counter * GOLD)


def unit(k: torch.Tensor, col: int = 0) -> torch.Tensor:
    """Uniform float32 strictly inside (0, 1) from key `k` and column `col`."""
    h = mix(k + _s64((col + 1) * 0xD1B54A32D192ED03))
    return (((h >> 40) & 0xFFFFFF).to(torch.float32) + 0.5) * _INV24


def unit2(k: torch.Tensor, col: int = 0):
    """Two independent uniforms from one hash (24 bits each)."""
    h = mix(k + _s64((col + 1) * 0xD1B54A32D192ED03))
    a = (((h >> 40) & 0xFFFFFF).to(torch.float32) + 0.5) * _INV24
    b = (((h >> 8) & 0xFFFFFF).to(torch.float32) + 0.5) * _INV24
    return a, b


def normal_from_unit(u: torch.Tensor) -> torch.Tensor:
    return 1.4142135623730951 * torch.erfinv(2.0 * u - 1.0)


_COLS: dict = {}


def units(k: torch.Tensor, ncol: int) -> torch.Tensor:
    """`ncol` uniforms per key in one hash: result[..., j] == unit(k, j)."""
    ck = (ncol, k.device)
    if ck not in _COLS:
        _COLS[ck] = torch.tensor([_s64((j + 1) * 0xD1B54A32D192ED03) for j in range(ncol)], dtype=torch.long, device=k.device)
    h = mix(k.unsqueeze(-1) + _COLS[ck])
    return (((h >> 40) & 0xFFFFFF).to(torch.float32) + 0.5) * _INV24
