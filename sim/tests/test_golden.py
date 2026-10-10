"""Golden-trajectory test: the M2 dynamics are frozen. See sim/tests/golden.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sim.tests import golden  # noqa: E402

DEVICES = ["cpu", pytest.param("cuda", marks=pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available"))]


@pytest.mark.parametrize("device", DEVICES)
def test_golden_trajectories(device):
    refs = {k: v for k, v in golden.load().items() if k.split("|")[0] == device}
    assert refs, f"no stored golden for {device}; generate with `python -m sim.tests.golden --write`"
    got = golden.compute(device)
    report = []
    for ref_key, ref in refs.items():
        bad = [c for c in got if ref[c]["sha256"] != got[c]["sha256"] or ref[c]["generated"] != got[c]["generated"]]
        if not bad:
            return
        report.append((ref_key, {c: (got[c]["sums"], ref[c]["sums"]) for c in bad[:2]}))
    pytest.fail(f"trajectory changed on {golden.platform_key(device)}: {report}")
