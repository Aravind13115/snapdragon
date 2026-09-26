# PHASE 2.7 REPORT — Monitoring optimization + decision evidence
Date (UTC): 2026-09-26. No process was modified. No process was terminated.
No process was suspended. No Snapdragon firmware was modified.

## 1. Sampler bottleneck (measured, not guessed; 261–273 procs)

| Stage | Time |
|---|---|
| `pids()` discovery | 1 ms |
| `process_iter` + attrs (name/mem/status/username) | ~2.9 s |
| `cpu_percent` pass | ~0.96 s |
| `memory_percent` pass | ~1.12 s |
| `status()` pass | ~1.82 s |
| `io_counters()` all | ~1.06 s |
| `arch_of` all (cached) | ~0 s |
| ORT batch ×261 | ~1.6 ms |
| sort + JSON serialize | ~0.3 ms |
| Full old pass (`top_processes` + enrich) | ~5.4 s, run 2× per cycle |

Correction to earlier diagnosis: the bulk is Windows per-process API
iteration itself, NOT username/SID lookups (username delta ≈ 0 s).

## 2. Optimization performed (`telemetry/sampler.py`, new)

- PID-keyed cache of reused `psutil.Process` objects; identity/metadata
  (name, arch, username) fetched once per (pid, create_time).
- FAST loop (5 s): 1 ms `pids()` diff → drop dead, add new, poll cpu+mem
  for active procs only; idle procs (cpu < 0.5% × 3 ticks) skip 2 of 3 ticks.
- SLOW loop (20 s, alternating halves): status/username/io refresh.
- PID reuse detected via create_time mismatch → full re-fetch; disappearance
  bounded by one fast tick via set diff.
- `features.build(..., io_total=)` accepts cached disk totals (default still
  live-queries; existing callers/tests unaffected) → enrich 1.16 s → 0.08 s.
- `top_processes()` retained unchanged for tests/compat.
- Safety philosophy, thresholds, model: untouched.

## 3/4. Before / after (actual measurements)

| Metric | Before | After |
|---|---|---|
| Sampling pass | 5.4 s full scan ×2 sorts | fast ~0.4–1 s tiered; slow ~2–3 s / 20 s |
| Enrich 200 rows | 1.16 s | 0.08 s (14×) |
| App CPU (machine) | ~6–8% bursts | **~1.0% steady (60 s avg)** |
| App RAM | ~69 MB | ~72 MB |
| API latency | <160 ms | <160 ms (unchanged, cache-served) |

Bugs found by tests during this phase (fixed): sampler rows emitted
UNNORMALIZED per-core CPU (up to 864%) — normalization restored to match
`top_processes()`; app.py `_sampler` name collision killed the sampler
thread (found via stderr capture); dashboard unhandled fetch rejection
(intervals now retry).

## 5. Decision-log implementation

- `ai/decision_log.py`: `logs/ai_decisions.jsonl` (JSONL, rotation at
  5000→3000 lines), top-40 rows per pass. Schema: timestamp, pid, process,
  architecture, model_class, raw_confidence, familiarity, familiarity_level,
  final_confidence, safety_state, recommendation, reason, backend.
  NO username or personal data.
- `GET /api/decisions?limit=N`: localhost-only, read-only, tail of log.
- Dashboard "AI Decision History" card (model vote vs safety decision,
  15 s refresh). 3600 records observed live.

## 6. Browser verification status: VERIFIED (headless Edge)

Rendered `http://127.0.0.1:8099/` via Edge `--headless=new --dump-dom`
with virtual-time budget: 36 KB DOM, all cards (AI Engine, Workload
Analysis, Process Table 50 rows, Decision History 12 rows, summary
"analyzed 200"), CPU FALLBACK shown, DEMO DATA banner present, trust
status rendered — **zero console errors** after the fetch-retry fix
(one transient teardown rejection found and fixed first).
Limitation: interactive demo-mode clicking not captured headless; demo
API outputs verified separately for all 5 sets.

## 7–9. Tests: 50 total, 0 failures, 1 warning (live-skew, known)

- test_phase2: 10/10 · test_phase25: 10/10 · test_phase27 (new): 10/10
  (caching, PID reuse, disappearance, log write, decisions API, schema,
  dashboard history, overhead, no-destructive-calls, safety no-regression)
- test_integration: 20/20 (re-ran after every change)
- Warning: live model-vote skew to DEFERRABLE on idle machine (population
  effect; balanced-probe spread verified; all affected rows PROTECT/REVIEW).

## 10. Live AI distribution

Model votes: PROTECTED ~15 / DEFERRABLE ~179 / USER_IMPORTANT ~3 /
FLEXIBLE ~1 (idle-machine skew, honest). Safety: PROTECT 138 / REVIEW 62 /
OBSERVE 0 / CANDIDATE 0. Thresholds NOT loosened; distribution NOT hidden.
Honest candidate path demonstrated only by SIMULATED DEMO centroid workload
(SyncClient FLEXIBLE 0.9893 → CANDIDATE; Mystery wild vector → PROTECT).

## 11. Snapdragon/QNN status

Unchanged: QNN UNAVAILABLE, NPU UNAVAILABLE, CPU FALLBACK — correct on
Intel. QNN abstraction untouched and still hardware-gated.

## 12. Remaining limitations

1. ~1% steady CPU is good but still polling-based; event-driven or
   ETW-based sampling is future work.
2. Live decisions remain almost all PROTECT/REVIEW by design (no labelled
   real data to be bolder against).
3. Decision log is local-only evidence; no remote/persistent store.
4. ARM/QNN paths still hardware-unvalidated.
