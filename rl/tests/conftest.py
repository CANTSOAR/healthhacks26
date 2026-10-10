import json

import pytest
import torch

from rl.common import TERMS

torch.set_num_threads(2)


@pytest.fixture(scope="session")
def scales():
    """Unit-ish scales so tests do not depend on rl/reward_scales.json existing."""
    s = {"cost": 30000.0, "wait": 400.0, "lwbs": 0.3, "safety": 0.05, "boarding": 0.2, "staff": 1.0, "revenue": 30000.0, "labor": 3000.0}
    return {"scales": s, "p95_wait_threshold_min": 120.0, "sim_fingerprint": "test"}
