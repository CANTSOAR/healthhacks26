"""WS /ws/sim: one live simulation per connection (contracts/api.md)."""
from __future__ import annotations

import asyncio
import json
import math
import time

from fastapi import WebSocket, WebSocketDisconnect

from . import cache, runs

MAX_FPS = 30.0        # above this tick rate snapshots are skipped while the simulation keeps its pace
MAX_SPEED = 5000.0
MAX_BURST = 288       # ticks simulated in one worker call at most (one simulated day)
FRAME_S = 0.07        # ... and never more than about this much wall time per call


class Session:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.run: runs.Run | None = None
        self.steps = 0
        self.wake = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.send_lock = asyncio.Lock()
        self.tick_cost = 0.01     # seconds of wall time per simulated tick (running average)

    # speed and pause live on the run, so a later socket that attaches resumes exactly as this one left it
    @property
    def speed(self) -> float:
        return self.run.speed if self.run is not None else 12.0

    @speed.setter
    def speed(self, v: float) -> None:
        if self.run is not None:
            self.run.speed = v

    @property
    def paused(self) -> bool:
        return self.run.paused if self.run is not None else False

    @paused.setter
    def paused(self, v: bool) -> None:
        if self.run is not None:
            self.run.paused = v

    # ---------------------------------------------------------------- io
    async def send_raw(self, text: str) -> None:
        async with self.send_lock:
            await self.ws.send_text(text)

    async def send(self, msg: dict) -> None:
        await self.send_raw(cache.dumps(msg))

    async def error(self, message: str) -> None:
        await self.send(dict(type="error", message=str(message)))

    # ---------------------------------------------------------------- loop
    def _advance(self, run: runs.Run, n: int) -> tuple[list[str], int]:
        """Advance up to n ticks, but never more than fit in about one frame of wall time, so a simulator that
        cannot keep up with the requested speed still sends a steady stream of snapshots. Returns (frames, ticks done)."""
        n = max(1, min(n, int(FRAME_S / max(self.tick_cost, 1e-4)) or 1))
        t0 = time.perf_counter()
        frames = [cache.dumps(m) for m in run.advance(n, snapshot=True)]
        cost = (time.perf_counter() - t0) / n
        self.tick_cost = cost if self.tick_cost <= 0 else 0.8 * self.tick_cost + 0.2 * cost
        return frames, n

    async def _loop(self, run: runs.Run) -> None:
        next_at = time.monotonic()
        try:
            while not run.finished and self.run is run:
                active = (not self.paused) and self.speed > 0
                if not active and self.steps <= 0:
                    self.wake.clear()
                    await self.wake.wait()
                    next_at = time.monotonic()
                    continue
                if not active:
                    self.steps -= 1
                    n, interval = 1, 0.0
                else:
                    self.steps = 0
                    speed = self.speed
                    n = 1 if speed <= MAX_FPS else min(MAX_BURST, int(math.ceil(speed / MAX_FPS)))
                frames, done = await asyncio.to_thread(self._advance, run, n)
                if active:
                    interval = done / speed
                for f in frames:
                    await self.send_raw(f)
                next_at += interval
                delay = next_at - time.monotonic()
                if delay <= 0:
                    next_at = time.monotonic()     # cannot keep up: run as fast as the simulator allows
                    await asyncio.sleep(0)
                    continue
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=delay)
                    next_at = time.monotonic()     # a control message arrived: re-pace from now
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except (WebSocketDisconnect, RuntimeError):
            return                                  # socket went away mid-send
        except Exception as e:  # noqa: BLE001
            try:
                await self.error(f"simulation stopped: {type(e).__name__}: {str(e)[:200]}")
            except Exception:  # noqa: BLE001
                pass

    async def _stop_loop(self) -> None:
        t, self.task = self.task, None
        if t is not None and not t.done():
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    # ---------------------------------------------------------------- messages
    async def on_start(self, msg: dict) -> None:
        await self._leave()
        ok, why = runs.sim_available()
        if not ok:
            await self.error(f"simulator unavailable: {why}")
            return
        scenario = str(msg.get("scenario") or "normal_week")
        try:
            seed = int(msg.get("seed") or 0)
            days = int(msg["days"]) if msg.get("days") else None
        except (TypeError, ValueError):
            await self.error("seed and days must be integers")
            return
        manager = str(msg.get("manager") or "human")
        notes = []
        try:
            run = await asyncio.to_thread(runs.Run, scenario, seed, msg.get("hospital_id") or None, "human", days)
        except Exception as e:  # noqa: BLE001
            await self.error(f"could not start '{scenario}': {type(e).__name__}: {str(e)[:300]}")
            return
        if manager != "human":
            try:
                await asyncio.to_thread(run.set_manager, manager)
            except Exception as e:  # noqa: BLE001
                notes.append(f"manager '{manager}' could not be loaded ({str(e)[:200]}); you are in control")
        self.run = runs.register(run)
        run.owner = self
        self._set_speed(msg.get("speed", 12))
        self.paused, self.steps = False, 0
        header, first, ack = await asyncio.to_thread(lambda: (cache.dumps(run.header()), cache.dumps(dict(type="snapshot", snapshot=run.snapshot())),
                                                              cache.dumps(run.hour_msg(ack=True))))
        await self.send_raw(header)
        for n in run.notes + notes:
            await self.error(n)
        await self.send_raw(first)
        await self.send_raw(ack)
        self.task = asyncio.create_task(self._loop(run))

    async def _leave(self) -> None:
        """Stop driving the current run (if any). The run stays in the registry, paused at its tick, and can be attached again."""
        await self._stop_loop()
        run, self.run = self.run, None
        if run is not None and run.owner is self:
            runs.disconnect(run)

    async def kicked(self, run: runs.Run) -> None:
        """Another socket attached to our run."""
        if self.run is run:
            await self._stop_loop()
            self.run = None
            try:
                await self.send(dict(type="error", code="detached", run_id=run.run_id,
                                     message="this run was attached from another connection; this socket no longer drives it"))
            except Exception:  # noqa: BLE001
                pass

    async def on_attach(self, msg: dict) -> None:
        rid = str(msg.get("run_id") or "")
        try:
            run = runs.get_run(rid)
        except KeyError:
            await self.send(dict(type="error", code="run_gone", run_id=rid,
                                 message=f"run '{rid}' is no longer available (it expired after its connection closed, or the server restarted)"))
            return
        if run is not self.run:
            await self._leave()
            old = run.owner
            if old is not None and old is not self:
                await old.kicked(run)
        else:
            await self._stop_loop()
        self.run, run.owner, run.connected = run, self, True
        run.last_seen = time.time()
        self.steps = 0

        def build():
            with run.lock:
                h = run.header()
                h["attached"] = True
                snap = run._quiet_snapshot()
                run.clock = snap.get("clock") or run.clock
                return cache.dumps(h), cache.dumps(dict(type="snapshot", snapshot=snap)), cache.dumps(run.hour_msg(ack=True)), \
                    cache.dumps(run.summary(final=run.finished))
        header, snap, ack, summary = await asyncio.to_thread(build)
        await self.send_raw(header)
        await self.send_raw(snap)
        await self.send_raw(ack)
        await self.send_raw(summary)
        self.task = asyncio.create_task(self._loop(run))

    def _set_speed(self, v) -> None:
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ValueError("ticks_per_second must be a number")
        if not math.isfinite(v):
            raise ValueError("ticks_per_second must be finite")
        self.speed = max(0.0, min(MAX_SPEED, v))

    async def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "start":
            await self.on_start(msg)
            return
        if kind == "attach":
            await self.on_attach(msg)
            return
        run = self.run
        if run is None:
            await self.error(f"no simulation is running; send a start message first (got '{kind}')")
            return
        if kind == "action":
            actions = msg.get("actions")
            if not isinstance(actions, dict):
                await self.error("action needs an `actions` object of {head: option index}")
                return
            for e in run.set_actions(actions):
                await self.error(e)
            if run.policy is not None:
                await self.error(f"manager '{run.manager['id']}' is in control; your changes are held until you take over")
            await self.send(run.hour_msg(ack=True))
        elif kind == "manager":
            info = await asyncio.to_thread(run.set_manager, str(msg.get("manager") or "human"))
            ack = run.hour_msg(ack=True)
            ack["manager_info"] = info
            await self.send(ack)
        elif kind == "speed":
            self._set_speed(msg.get("ticks_per_second", msg.get("speed", 0)))
            self.wake.set()
        elif kind == "pause":
            self.paused = True
            self.wake.set()
        elif kind == "resume":
            self.paused = False
            if self.speed <= 0:
                self.speed = 12.0
            self.wake.set()
        elif kind == "step":
            if (not self.paused) and self.speed > 0:
                await self.error("step only applies while paused")
            else:
                self.steps += 1
                self.wake.set()
        elif kind == "inject":
            res = await asyncio.to_thread(run.inject, str(msg.get("event")), msg.get("params") if isinstance(msg.get("params"), dict) else None)
            ack = run.hour_msg(ack=True)
            ack["injected"] = res
            await self.send(ack)
        elif kind == "detail":
            ent = msg.get("entity") if isinstance(msg.get("entity"), dict) else {}
            await self.send(await asyncio.to_thread(run.detail, str(ent.get("kind")), ent.get("id")))
        elif kind == "stop":
            await self._stop_loop()
            self.paused = True          # a stopped run that is attached again stays stopped until resumed
            await self.send(await asyncio.to_thread(run.summary, True))
        else:
            await self.error(f"unknown message type '{kind}'")

    async def serve(self) -> None:
        await self.ws.accept()
        try:
            while True:
                raw = await self.ws.receive_text()
                try:
                    msg = json.loads(raw)
                    if not isinstance(msg, dict):
                        raise ValueError("message must be a JSON object")
                except ValueError as e:
                    await self.error(f"bad message: {str(e)[:120]}")
                    continue
                try:
                    await self.handle(msg)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    raise
                except Exception as e:  # noqa: BLE001 - every failure is reported, never fatal to the socket
                    msgtxt = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
                    await self.error(f"{msg.get('type')}: {str(msgtxt)[:300]}")
        except WebSocketDisconnect:
            pass
        except RuntimeError:
            pass   # receive after close
        finally:
            await self._leave()


async def ws_sim(ws: WebSocket) -> None:
    await Session(ws).serve()
