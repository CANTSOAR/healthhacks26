"""Language-model providers behind one interface.

Which one is used is decided at startup purely by which credential is present (no flag):
  1. Bedrock   - AWS credentials resolve (boto3 `bedrock-runtime`, Converse API; works for Amazon Nova and Claude)
  2. Anthropic - ANTHROPIC_API_KEY is set (official `anthropic` SDK, Messages API)
  3. Offline   - neither; the deterministic matcher and authored wording do everything

Model IDs are configurable: BEDROCK_MODEL_ID, ANTHROPIC_MODEL.
Defaults:
  BEDROCK_MODEL_ID = us.amazon.nova-pro-v1:0   (the workshop AWS account lists Amazon Nova models, see
                     research/resource-feasibility-2026-10-10.md; set e.g. us.amazon.nova-micro-v1:0 for a cheaper
                     model, or a Claude inference-profile ID if the account has Anthropic access - Bedrock Claude IDs
                     take the `anthropic.` prefix, e.g. anthropic.claude-opus-5-5 / us.anthropic.claude-opus-5-5)
  ANTHROPIC_MODEL  = claude-opus-5-5

A provider only ever returns text. It never decides what is disclosed: callers pass it fact IDs and
approved wording, and verify what comes back. Any failure raises ProviderError; callers fall back to
the offline path for that call and report `fallback: true`.

Not run against the real services in this build (no credentials were present); exercised in tests
against faked clients.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

DEFAULT_BEDROCK_MODEL = "us.amazon.nova-pro-v1:0"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
FAIL_COOLDOWN_S = 45.0          # after 2 consecutive failures, skip the online call for this long


class ProviderError(Exception):
    pass


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
    live = False

    def __init__(self):
        self.last_error: str | None = None
        self.last_ok: float | None = None
        self._fails = 0
        self._skip_until = 0.0
        self._lock = threading.Lock()

    # subclasses implement _complete
    def _complete(self, system: str, user: str, max_tokens: int, schema: dict | None) -> str:
        raise ProviderError("offline provider has no model")

    def complete(self, system: str, user: str, max_tokens: int = 1024, schema: dict | None = None) -> str:
        if not self.live:
            raise ProviderError("offline")
        if time.time() < self._skip_until:
            raise ProviderError(f"{self.name} cooling down after errors: {self.last_error}")
        try:
            out = self._complete(system, user, max_tokens, schema)
            if not isinstance(out, str) or not out.strip():
                raise ProviderError("empty reply")
        except Exception as e:  # noqa: BLE001 - any failure means: fall back to offline for this call
            with self._lock:
                self._fails += 1
                self.last_error = f"{type(e).__name__}: {str(e)[:300]}"
                if self._fails >= 2:
                    self._skip_until = time.time() + FAIL_COOLDOWN_S
            raise ProviderError(self.last_error) from e
        with self._lock:
            self._fails = 0
            self.last_ok = time.time()
        return out

    def complete_json(self, system: str, user: str, max_tokens: int = 1024, schema: dict | None = None) -> dict:
        return extract_json(self.complete(system, user, max_tokens, schema))

    def status(self) -> dict:
        d = {"live": self.live, "provider": self.name, "model": self.model}
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

    def __init__(self, client=None, model: str | None = None, region: str | None = None):
        super().__init__()
        self.model = model or os.environ.get("BEDROCK_MODEL_ID") or DEFAULT_BEDROCK_MODEL
        # models to try, in order, when the account refuses the preferred one (workshop accounts list models they
        # cannot actually invoke); a refused model is dropped for the life of the process
        extra = [m.strip() for m in (os.environ.get("BEDROCK_FALLBACK_MODEL_IDS") or "").split(",") if m.strip()]
        self.models = [self.model] + [m for m in extra if m != self.model]
        self.region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        self._client = client

    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config
            self._client = boto3.client("bedrock-runtime", region_name=self.region,
                                        config=Config(connect_timeout=4, read_timeout=30, retries={"max_attempts": 2}))
        return self._client

    def _complete(self, system, user, max_tokens, schema):
        if schema is not None:
            system = system + "\n\nReply with ONE JSON object only, no prose, matching this JSON schema:\n" + json.dumps(schema)
        resp, last = None, None
        for model in list(self.models):
            try:
                resp = self.client().converse(
                    modelId=model,
                    system=[{"text": system}],
                    messages=[{"role": "user", "content": [{"text": user}]}],
                    inferenceConfig={"maxTokens": max_tokens},      # no sampling params: some models reject them
                )
                self.model = model
                break
            except Exception as e:  # noqa: BLE001
                last = e
                denied = type(e).__name__ in ("AccessDeniedException", "ResourceNotFoundException") or "AccessDenied" in str(e)
                if denied and len(self.models) > 1:
                    self.models.remove(model)      # not usable on this account: do not try it again
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

    def __init__(self, client=None, model: str | None = None):
        super().__init__()
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
        self._client = client

    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(timeout=30.0, max_retries=1)
        return self._client

    def _complete(self, system, user, max_tokens, schema):
        # Current Claude models: thinking is adaptive by default (cannot be disabled on Opus 5.5), sampling
        # parameters are rejected, and depth is steered with output_config.effort. Short role-play and
        # classification calls run at low effort. Structured replies use output_config.format.
        output_config: dict = {"effort": os.environ.get("ANTHROPIC_EFFORT") or "low"}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        resp = self.client().messages.create(
            model=self.model,
            max_tokens=max(max_tokens, 2048),            # leaves room for adaptive thinking
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config=output_config,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise ProviderError("model declined the request (stop_reason=refusal)")
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")


def aws_credentials_resolve() -> bool:
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
