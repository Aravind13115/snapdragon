"""Tiered process sampler: fast/slow loops with PID-keyed metadata cache.

Design (Phase 2.7, observation-only):
  * FAST tick (default 5s): 1ms `pids()` discovery diff -> drop dead pids,
    create entries for new pids (name/create_time/arch once), then poll
    cpu+mem for ACTIVE processes only. Idle procs (cpu < 0.5% three ticks
    running) are skipped up to IDLE_SKIP ticks; their last values persist.
  * SLOW tick (default 20s): refresh display-only metadata for all cached
    entries (status, username, io totals). Arch is cached forever per
    (pid, create_time) — a process never changes architecture.
  * PID reuse: cache key is the pid, but every entry stores create_time;
    any mismatch (or reappearance after death) is treated as a NEW process
    and fully re-fetched. Dead pids are dropped every fast tick via the
    pids() set diff, so disappearance is bounded by one fast interval.

Cost vs full `top_processes()` scan: skips repeated name/status/username
resolution and idle re-polling; sorting/filtering is in-memory.
"""
from __future__ import annotations

import time

import psutil

from ai import features as _feat

IDLE_CPU = 0.5  # % of total machine capacity (values are normalized, see below)

try:
    _NCPU = psutil.cpu_count(logical=True) or 1
except Exception:
    _NCPU = 1


class Sampler:
    def __init__(self, fast_interval: float = 5.0, slow_interval: float = 20.0,
                 idle_skip: int = 2):
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.idle_skip = idle_skip
        self.entries: dict[int, dict] = {}
        self.last_slow = 0.0
        self.last_fast_ts = 0.0
        self.stats = {"fast_ticks": 0, "polled": 0, "skipped": 0,
                      "added": 0, "removed": 0, "last_fast_s": 0.0}

    # ------------------------------------------------------------ ticks ----
    def fast_tick(self) -> dict:
        t0 = time.perf_counter()
        live = set(psutil.pids())
        cached = set(self.entries)
        for pid in cached - live:
            self.entries.pop(pid, None)
            self.stats["removed"] += 1
        for pid in live - cached:
            self._add(pid)
        polled = skipped = 0
        for pid, e in self.entries.items():
            try:
                if e["idle_streak"] >= 3 and e["skip_left"] > 0:
                    e["skip_left"] -= 1
                    e["stale"] += 1
                    skipped += 1
                    continue
                p = e["proc"]
                if p.create_time() != e["create_time"]:
                    self._refresh_entry(pid, e)  # PID reuse -> full re-fetch
                    polled += 1
                    continue
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_percent()
                # psutil reports per-process CPU against ONE core (up to
                # 100% x ncpu). Normalize to % of total machine capacity so
                # rows match top_processes()/Task-Manager-style readings.
                e["cpu"] = round(max(0.0, (cpu or 0.0) / _NCPU), 2)
                e["mem"] = round(max(0.0, mem or 0.0), 2)
                e["stale"] = 0
                e["skip_left"] = self.idle_skip
                if e["cpu"] < IDLE_CPU:
                    e["idle_streak"] += 1
                else:
                    e["idle_streak"] = 0
                polled += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                e["gone"] = e.get("gone", 0) + 1
                if e["gone"] >= 3:
                    self.entries.pop(pid, None)
                    self.stats["removed"] += 1
        if time.time() - self.last_slow >= self.slow_interval:
            self.slow_tick()
        self.stats["fast_ticks"] += 1
        self.stats["polled"] = polled
        self.stats["skipped"] = skipped
        self.stats["last_fast_s"] = round(time.perf_counter() - t0, 3)
        self.last_fast_ts = time.time()
        return dict(self.stats)

    def slow_tick(self) -> None:
        # Halved: alternate halves each run so a slow pass costs ~half;
        # metadata (status/username/io) goes stale ≤ 2 slow intervals max.
        self._slow_parity = 1 - getattr(self, "_slow_parity", 0)
        items = list(self.entries.items())[self._slow_parity::2]
        for pid, e in items:
            try:
                p = e["proc"]
                e["status"] = p.status()
                try:
                    e["username"] = p.username()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    e["username"] = "?"
                try:
                    io = p.io_counters()
                    e["io_total"] = (io.read_bytes or 0) + (io.write_bytes or 0)
                except Exception:
                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                self.entries.pop(pid, None)
                self.stats["removed"] += 1
        self.last_slow = time.time()

    # ---------------------------------------------------------- entries ----
    def _add(self, pid: int) -> None:
        e = {"proc": None, "cpu": 0.0, "mem": 0.0, "stale": 0,
             "idle_streak": 0, "skip_left": self.idle_skip, "gone": 0}
        self.entries[pid] = e
        self._refresh_entry(pid, e)
        self.stats["added"] += 1

    def _refresh_entry(self, pid: int, e: dict) -> None:
        """Full (re)fetch of identity + metadata for one pid."""
        try:
            p = psutil.Process(pid)
            e["proc"] = p
            e["create_time"] = p.create_time()
            e["name"] = p.name() or "?"
            e["status"] = p.status()
            try:
                e["username"] = p.username()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                e["username"] = "?"
            try:
                io = p.io_counters()
                e["io_total"] = (io.read_bytes or 0) + (io.write_bytes or 0)
            except Exception:
                e["io_total"] = None
            try:
                e["mem"] = round(max(0.0, p.memory_percent() or 0.0), 2)
            except Exception:
                pass
            e["arch"] = _feat.arch_of(pid)
            e["idle_streak"] = 0
            e["skip_left"] = self.idle_skip
            e["stale"] = 0
            e["gone"] = 0
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            self.entries.pop(pid, None)

    # ------------------------------------------------------------ rows -----
    def rows(self, limit: int = 50, sort: str = "cpu") -> dict:
        out = []
        for pid, e in self.entries.items():
            if e.get("proc") is None:
                continue
            out.append({
                "pid": pid, "name": e.get("name", "?"),
                "cpu_pct": e.get("cpu", 0.0), "mem_pct": e.get("mem", 0.0),
                "status": e.get("status", "?"), "username": e.get("username", "?"),
                "arch": e.get("arch", "Unknown"),
                "stale_s": round(time.time() - self.last_fast_ts, 1),
                "_io_total": e.get("io_total"),
            })
        key = {"cpu": lambda r: r["cpu_pct"],
               "mem": lambda r: r["mem_pct"]}.get(sort, lambda r: r["cpu_pct"])
        out.sort(key=key, reverse=True)
        return {"simulated": False, "count": len(out),
                "rows": out[: max(1, min(limit, 200))],
                "sampler": {"polled": self.stats["polled"],
                            "skipped": self.stats["skipped"],
                            "fast_s": self.stats["last_fast_s"]}}
