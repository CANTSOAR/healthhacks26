"""Actor-critic network for the factored, masked action space. Plain torch (works on 2.2 and 2.8)."""
from __future__ import annotations

import torch
import torch.nn as nn


def mlp(inp, hidden, layers, out, out_gain=1.0):
    mods, d = [], inp
    for _ in range(layers):
        lin = nn.Linear(d, hidden)
        nn.init.orthogonal_(lin.weight, 2 ** 0.5)
        nn.init.zeros_(lin.bias)
        mods += [lin, nn.Tanh()]
        d = hidden
    last = nn.Linear(d, out)
    nn.init.orthogonal_(last.weight, out_gain)
    nn.init.zeros_(last.bias)
    mods.append(last)
    return nn.Sequential(*mods)


class ActorCritic(nn.Module):
    """Separate actor and critic MLPs over a shared, saved observation normaliser.

    The actor emits one block of logits per action head. Value targets are normalised with a
    running mean/variance of returns that is saved with the policy.
    """

    def __init__(self, obs_dim: int, head_sizes: list[int], hidden: int = 256, layers: int = 2, defaults: list[int] | None = None):
        super().__init__()
        self.obs_dim, self.head_sizes = int(obs_dim), [int(x) for x in head_sizes]
        self.actor = mlp(obs_dim, hidden, layers, sum(self.head_sizes), 0.01)
        self.critic = mlp(obs_dim, hidden, layers, 1, 1.0)
        self.register_buffer("obs_mean", torch.zeros(obs_dim))
        self.register_buffer("obs_var", torch.ones(obs_dim))
        self.register_buffer("obs_count", torch.tensor(1e-4))
        self.register_buffer("ret_mean", torch.zeros(()))
        self.register_buffer("ret_var", torch.ones(()))
        self.register_buffer("ret_count", torch.tensor(1e-4))
        if defaults is not None:                       # bias toward the default action at init
            with torch.no_grad():
                o = 0
                for n, d in zip(self.head_sizes, defaults):
                    self.actor[-1].bias[o + int(d)] = 1.5
                    o += n

    @torch.no_grad()
    def update_obs_stats(self, obs: torch.Tensor):
        self._update("obs", obs.reshape(-1, obs.shape[-1]))

    @torch.no_grad()
    def update_ret_stats(self, ret: torch.Tensor):
        self._update("ret", ret.reshape(-1))

    def _update(self, name, x):
        mean, var, count = getattr(self, name + "_mean"), getattr(self, name + "_var"), getattr(self, name + "_count")
        bm, bv, bc = x.mean(0), x.var(0, unbiased=False), float(x.shape[0])
        tot = count + bc
        delta = bm - mean
        new_mean = mean + delta * bc / tot
        new_var = (var * count + bv * bc + delta ** 2 * count * bc / tot) / tot
        mean.copy_(new_mean), var.copy_(new_var), count.copy_(tot)

    def norm(self, obs):
        return ((obs - self.obs_mean) / torch.sqrt(self.obs_var + 1e-6)).clamp(-8.0, 8.0)

    def logits(self, obs) -> list[torch.Tensor]:
        return list(torch.split(self.actor(self.norm(obs)), self.head_sizes, dim=-1))

    def value_norm(self, obs) -> torch.Tensor:
        return self.critic(self.norm(obs)).squeeze(-1)

    def value(self, obs) -> torch.Tensor:
        return self.value_norm(obs) * torch.sqrt(self.ret_var + 1e-8) + self.ret_mean

    def act(self, obs, deterministic=False):
        """-> actions LongTensor[B, H], per-head log-probs [B, H]."""
        acts, lps = [], []
        for lg in self.logits(obs):
            lp = torch.log_softmax(lg, -1)
            a = lp.argmax(-1) if deterministic else torch.multinomial(lp.exp(), 1).squeeze(-1)
            acts.append(a)
            lps.append(lp.gather(-1, a.unsqueeze(-1)).squeeze(-1))
        return torch.stack(acts, -1), torch.stack(lps, -1)

    def evaluate(self, obs, actions):
        """-> per-head log-probs [N, H], per-head entropies [N, H]."""
        lps, ents = [], []
        for i, lg in enumerate(self.logits(obs)):
            lp = torch.log_softmax(lg, -1)
            lps.append(lp.gather(-1, actions[:, i:i + 1]).squeeze(-1))
            ents.append(-(lp.exp() * lp).sum(-1))
        return torch.stack(lps, -1), torch.stack(ents, -1)
