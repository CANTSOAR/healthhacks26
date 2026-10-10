"""Language-model providers behind one interface.

Which one is used is decided at startup purely by which credential is present (no flag):
  1. Bedrock   - AWS credentials resolve (boto3 `bedrock-runtime`, Converse API; works for Amazon Nova and Claude)
  2. Anthropic - ANTHROPIC_API_KEY is set (official `anthropic` SDK, Messages API)
  3. Offline   - neither; the deterministic matcher and authored wording do everything

Model IDs are configurable: BEDROCK_MODEL_ID, ANTHROPIC_MODEL, and a second, faster model for the short per-turn
calls (intent labelling, grounding verification, patient wording): BEDROCK_FAST_MODEL_ID / ANTHROPIC_FAST_MODEL.
A call names a tier ("main" or "fast"); the fast tier falls back to the main model when no fast model is set or the
account refuses it. A call may also carry a short timeout (seconds); a timeout is a failure like any other.
Defaults:
  BEDROCK_MODEL_ID = us.amazon.nova-pro-v1:0   (the workshop AWS account lists Amazon Nova models, see
                     research/resource-feasibility-2026-10-10.md; set e.g. us.amazon.nova-micro-v1:0 for a cheaper
                     model, or a Claude inference-profile ID if the account has Anthropic access - Bedrock Claude IDs
                     take the `anthropic.` prefix, e.g. anthropic.claude-opus-5-5 / us.anthropic.claude-opus-5-5)
  ANTHROPIC_MODEL  = claude-opus-5-5

A provider only ever returns text. It never decides what is disclosed: callers pass it fact IDs and
approved wording, and verify what comes back. Any failure raises ProviderError; callers fall back to
the offline path for that call and report `fallback: true`.

The Bedrock path has been run against the real service (see encounter/eval/ONLINE_RESULTS.md); the Anthropic
path only against faked clients.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time

DEFAULT_BEDROCK_MODEL = "us.amazon.nova-pro-v1:0"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
FAIL_COOLDOWN_S = 45.0          # after 3 consecutive failures, skip the online call for this long
FAIL_LIMIT = 3


def turn_timeout_s() -> float:
    """Per-call timeout for the short calls made inside a patient turn (ENCOUNTER_LLM_TURN_TIMEOUT_S, default 6 s)."""
    try:
        return max(1.0, float(os.environ.get("ENCOUNTER_LLM_TURN_TIMEOUT_S") or 6.0))
    except ValueError:
        return 6.0


class ProviderError(Exception):
    pass


def under_test() -> bool:
    """True inside a pytest process. Test suites must never reach a real model, even when the developer's shell has
    credentials loaded from .env: under pytest, ambient AWS credentials do not count and no real client is ever built
    (tests inject fake clients). Set ENCOUNTER_ALLOW_NETWORK_IN_TESTS=1 to lift this deliberately."""
    return "pytest" in sys.modules and not (os.environ.get("ENCOUNTER_ALLOW_NETWORK_IN_TESTS") or "").strip()


def extract_json(text: str) -> dict:
    """Parse a JSON object out of a model reply (tolerates code fences and surrounding prose)."""
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("empty model reply")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    try:
        v = json.loads(t)
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    start = t.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        v = json.loads(t[start: i + 1])
                        if isinstance(v, dict):
                            return v
                    except Exception:
                        pass
                    break
        start = t.find("{", start + 1)
    raise ProviderError("model reply did not contain a JSON object")


class Provider:
    name = "offline"
    model: str | None = None
    fast_model: str | None = None
    live = False

    def __init__(self):
        self.last_error: str | None = None
        self.last_ok: float | None = None
        self.n_calls = 0                      # requests actually sent to the service (for reporting)
        self.calls_by_model: dict[str, int] = {}
        self._fails = 0
        self._skip_until = 0.0
        self._lock = threading.Lock()

    def _count(self, model: str | None) -> None:
        with self._lock:
            self.n_calls += 1
            self.calls_by_model[str(model)] = self.calls_by_model.get(str(model), 0) + 1

    def model_for(self, tier: str = "main") -> str | None:
        return (self.fast_model or self.model) if tier == "fast" else self.model

    # subclasses implement _complete
    def _complete(self, system: str, user: str, max_tokens: int, schema: dict | None, tier: str = "main",
                  timeout: float | None = None) -> str:
        raise ProviderError("offline provider has no model")

    def complete(self, system: str, user: str, max_tokens: int = 1024, schema: dict | None = None, tier: str = "main",
                 timeout: float | None = None) -> str:
        """One completion. `tier` picks the main or the fast model; `timeout` (seconds) bounds this call. Thread-safe."""
        if not self.live:
            raise ProviderError("offline")
        if time.time() < self._skip_until:
            raise ProviderError(f"{self.name} cooling down after errors: {self.last_error}")
        try:
            out = self._complete(system, user, max_tokens, schema, tier, timeout)
            if not isinstance(out, str) or not out.strip():
                raise ProviderError("empty reply")
        except Exception as e:  # noqa: BLE001 - any failure means: fall back to offline for this call
            with self._lock:
                self._fails += 1
                self.last_error = f"{type(e).__name__}: {str(e)[:300]}"
                if self._fails >= FAIL_LIMIT:
                    self._skip_until = time.time() + FAIL_COOLDOWN_S
            raise ProviderError(self.last_error) from e
        with self._lock:
            self._fails = 0
            self.last_ok = time.time()
        return out

    def complete_json(self, system: str, user: str, max_tokens: int = 1024, schema: dict | None = None, tier: str = "main",
                      timeout: float | None = None) -> dict:
        return extract_json(self.complete(system, user, max_tokens, schema, tier, timeout))

    def warm(self) -> None:
        """Prepare for a first call without making one (build clients in the background). No-op by default."""

    def status(self) -> dict:
        d = {"live": self.live, "provider": self.name, "model": self.model}
        if self.fast_model and self.fast_model != self.model:
            d["fast_model"] = self.fast_model
        if self.last_error:
            d["last_error"] = self.last_error
        return d


class OfflineProvider(Provider):
    name = "offline"
    live = False


class BedrockProvider(Provider):
    """Amazon Bedrock through the Converse API (model-agnostic: Nova, Claude, ...)."""
    name = "bedrock"
    live = True

    def __init__(self, client=None, model: str | None = None, region: str | None = None, fast_model: str | None = None):
        super().__init__()
        self.model = model or os.environ.get("BEDROCK_MODEL_ID") or DEFAULT_BEDROCK_MODEL
        # models to try, in order, when the account refuses the preferred one (workshop accounts list models they
        # cannot actually invoke); a refused model is dropped for the life of the process
        extra = [m.strip() for m in (os.environ.get("BEDROCK_FALLBACK_MODEL_IDS") or "").split(",") if m.strip()]
        self.models = [self.model] + [m for m in extra if m != self.model]
        # optional faster model for the short per-turn calls; tried first for tier="fast", then the list above
        self.fast_model = (fast_model or os.environ.get("BEDROCK_FAST_MODEL_ID") or "").strip() or None
        self.region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        self._client = client
        self._clients: dict[float, object] = {}

    def client(self, timeout: float | None = None):
        """One boto3 client per read timeout (boto3 sets timeouts on the client, not the call; clients are thread-safe).
        A client injected by a test is used for every timeout."""
        if self._client is not None:
            return self._client
        if under_test():
            raise ProviderError("real Bedrock clients are disabled under pytest")
        key = float(timeout or 60.0)
        with self._lock:
            c = self._clients.get(key)
        if c is None:
            import boto3
            from botocore.config import Config
            short = timeout is not None
            c = boto3.client("bedrock-runtime", region_name=self.region,
                             config=Config(connect_timeout=3 if short else 4, read_timeout=key,
                                           retries={"max_attempts": 1 if short else 2}, max_pool_connections=16))
            with self._lock:
                self._clients.setdefault(key, c)
                c = self._clients[key]
        return c

    def warm(self) -> None:
        """Import boto3 and build the clients off the request path, so the learner's first question does not pay for it."""
        if self._client is not None or under_test() or getattr(self, "_warmed", False):
            return
        self._warmed = True

        def go():
            try:
                self.client(turn_timeout_s())
                self.client()
            except Exception:  # noqa: BLE001 - warming is best effort
                pass
        threading.Thread(target=go, name="bedrock-warm", daemon=True).start()

    def _order(self, tier: str) -> list[str]:
        with self._lock:
            models = list(self.models)
            fast = self.fast_model
        if tier == "fast" and fast:
            return [fast] + [m for m in models if m != fast]
        return models

    def _drop(self, model: str) -> None:
        with self._lock:
            if model == self.fast_model:
                self.fast_model = None
            if model in self.models and len(self.models) > 1:
                self.models.remove(model)
                if self.model == model:
                    self.model = self.models[0]

    def _complete(self, system, user, max_tokens, schema, tier="main", timeout=None):
        if schema is not None:
            system = system + "\n\nReply with ONE JSON object only, no prose, matching this JSON schema:\n" + json.dumps(schema)
        resp, last = None, None
        order = self._order(tier)
        for i, model in enumerate(order):
            try:
                self._count(model)
                resp = self.client(timeout).converse(
                    modelId=model,
                    system=[{"text": system}],
                    messages=[{"role": "user", "content": [{"text": user}]}],
                    inferenceConfig={"maxTokens": max_tokens},      # no sampling params: some models reject them
                )
                if tier != "fast":
                    with self._lock:
                        self.model = model
                break
            except Exception as e:  # noqa: BLE001
                last = e
                denied = type(e).__name__ in ("AccessDeniedException", "ResourceNotFoundException") or "AccessDenied" in str(e)
                if denied and i < len(order) - 1:
                    self._drop(model)              # not usable on this account: do not try it again
                    continue
                raise
        if resp is None:
            raise last  # type: ignore[misc]
        blocks = (((resp or {}).get("output") or {}).get("message") or {}).get("content") or []
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and "text" in b)
        if (resp or {}).get("stopReason") in ("content_filtered", "guardrail_intervened"):
            raise ProviderError(f"bedrock stopped: {resp.get('stopReason')}")
        return text


class AnthropicProvider(Provider):
    """Anthropic Messages API via the official SDK."""
    name = "anthropic"
    live = True

    def __init__(self, client=None, model: str | None = None, fast_model: str | None = None):
        super().__init__()
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
        # optional faster model for the short per-turn calls (must accept output_config.effort, e.g. claude-haiku-5-5)
        self.fast_model = (fast_model or os.environ.get("ANTHROPIC_FAST_MODEL") or "").strip() or None
        self._client = client

    def client(self):
        if self._client is None:
            if under_test():
                raise ProviderError("real Anthropic clients are disabled under pytest")
            import anthropic
            self._client = anthropic.Anthropic(timeout=30.0, max_retries=1)
        return self._client

    def _complete(self, system, user, max_tokens, schema, tier="main", timeout=None):
        # Current Claude models: thinking is adaptive by default (cannot be disabled on Opus 5.5), sampling
        # parameters are rejected, and depth is steered with output_config.effort. Short role-play and
        # classification calls run at low effort. Structured replies use output_config.format.
        output_config: dict = {"effort": os.environ.get("ANTHROPIC_EFFORT") or "low"}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        client = self.client()
        if timeout is not None and hasattr(client, "with_options"):
            client = client.with_options(timeout=float(timeout), max_retries=0)
        model = self.model_for(tier)
        self._count(model)
        resp = client.messages.create(
            model=model,
            max_tokens=max(max_tokens, 2048),            # leaves room for adaptive thinking
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config=output_config,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise ProviderError("model declined the request (stop_reason=refusal)")
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")


def aws_credentials_resolve() -> bool:
    if under_test():
        return False
    # a Bedrock API key (bearer token) is a credential too; boto3 picks it up from this variable
    if (os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or "").strip():
        return True
    try:
        import boto3
        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


def select_provider() -> Provider:
    if aws_credentials_resolve():
        return BedrockProvider()
    if (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return AnthropicProvider()
    return OfflineProvider()


_provider: Provider | None = None
_plock = threading.Lock()


def get_provider() -> Provider:
    """The provider chosen at startup (first use). Tests call reset_provider()."""
    global _provider
    with _plock:
        if _provider is None:
            _provider = select_provider()
        return _provider


def reset_provider(provider: Provider | None = None) -> None:
    global _provider
    with _plock:
        _provider = provider


def voice_status() -> dict:
    live = bool((os.environ.get("ELEVENLABS_API_KEY") or "").strip())
    return {"live": live, "provider": "elevenlabs" if live else "browser"}
