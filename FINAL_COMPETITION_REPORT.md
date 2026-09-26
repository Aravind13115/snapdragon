# FINAL COMPETITION REPORT — Snapdragon AI Smart Process Manager
(Technical name: Snapdragon AI Adaptive Process Optimizer)
Prototype complete through Phase 5. Validated 2026-09-26 on Intel i5-1334U/x64.
No process was modified, terminated, or suspended at any stage.

# Executive Summary

A stability-first, fully local AI layer for Windows resource management:
real telemetry → 11-feature engineering → 1.9 KB ONNX MLP → temperature +
OOD calibration → PROTECT-first safety engine → advisory optimization
simulation, all behind a live dashboard. **68/68 tests pass.** The identical
model/backend stack targets the Snapdragon Hexagon NPU via QNN on HP
Snapdragon PCs; on this Intel machine it runs CPU FALLBACK and says so.

# Product Concept / Problem / Solution

Background work wastes resources, but users can't tell what's safe to defer.
This prototype answers that with contextual AI (foreground? battery?
emulated? familiar?) instead of CPU thresholds — then proves the decision
pipeline end-to-end through non-destructive simulation. Observe →
Understand → Predict → Protect → Simulate. Never Kill/Suspend/Disable.

# AI Architecture

MLP 11→16→8→4, synthetic-trained (4000 rows, deterministic), T=2.0 folded
into ONNX graph, RBF familiarity vs training centroids, final = calibrated
× familiarity, thresholds 0.85/0.50. Synthetic: 93.22% train / 87.38% test
(fit metric only — NOT real-world accuracy; stated everywhere it appears).

# Snapdragon Architecture

ONNX → ONNX Runtime → (QNNExecutionProvider when present) → Hexagon NPU.
`backend.select()` auto-switches; `bench.npu_scaffold()` marks NPU fields
REQUIRES_SNAPDRAGON_HARDWARE. Deployment wording: the model is deployed to
and executed by existing Hexagon silicon via the Qualcomm stack — nothing
modifies silicon, firmware, drivers, or kernel.

# Windows-on-Arm Architecture

IsWow64Process2-based labels (ARM64 Native/x64/x86-WOW64/Emulated/Unknown,
never guessed); `is_emulated` is one of eleven features; x86/x64 never
penalized. Code-complete, hardware-unvalidated on this x64 host.

# Safety Architecture

Allowlist → foreground → OOD → confidence floors → PROTECT/OBSERVE/REVIEW/
CANDIDATE; model vote vs final decision separate in code, API, UI, and logs;
`guard()` default-deny; STOP AI OPTIMIZATION disables simulation server-side
while monitoring continues. Adversarial 0.9999 votes cannot bypass (tested).

# Phase Results

- 2.5 VERIFIED: calibration/OOD/safety pipeline + separation + explainability.
- 2.7 VERIFIED: tiered sampler (~1% CPU from ~7%), decision log + API + history.
- 3 VERIFIED: simulator, 9 demo sets, GET-only preview/simulate, staged UI,
  no-intervention proven (113 PIDs, 0 changes).
- 4 ARCHITECTED / HARDWARE VALIDATION REQUIRED: abstraction, selection logic,
  bench scaffold, validation guide, 7 tests. No NPU execution claimed.
- 5 VERIFIED: final dashboard (status strip, engine card, safety ring,
  emergency stop), README rewrite, claim audit, 68/68 tests, zero-error
  headless-Edge render.

# Performance Measurements (verified, Intel)

Sampler ~1.0% steady CPU · ~70 MB RAM · API <160 ms · ORT single-row
0.024 ms / batch64 0.051 ms / load 13 ms · simulator 0.002 ms/call.
Projected Snapdragon figures: unmeasured (framework ready).

# Test Results

phase2 10 · phase25 10 · phase27 10 · phase3 11 · phase4 7 · integration 20
= 68 passed, 0 failed, 0–1 known live-skew warnings. Compile clean.
Security/destructive audit: zero hits. Browser DOM: all sections, no console errors.

# Demo Instructions

`python app.py` → http://127.0.0.1:8099/ → START DEMO (presenting) →
SIMULATE → projected bars → decision history → STOP AI OPTIMIZATION →
scenario sets. ~3 minutes. `logs/ai_decisions.jsonl` captures the session.

# Current Hardware Status

Intel dev: QNN UNAVAILABLE · NPU UNAVAILABLE · CPU FALLBACK (correct).
Snapdragon HP target: ARCHITECTED, validation procedure in
`docs/SNAPDRAGON_VALIDATION.md`.

# Verified Claims

Local-only AI · real telemetry/predictions · conservative safety behavior ·
1% monitoring CPU · 0.024 ms inference · CPU FALLBACK honesty · simulation
non-interference (measured).

# Projected Claims (labelled, unmeasured)

NPU latency/throughput · battery/CPU savings from future actions ·
real-world classification accuracy · ARM-specific behavior.

# Known Limitations

Synthetic training; live skews PROTECT/REVIEW; best-effort disk/net;
illustrative projections; no remote store; ~1% polling overhead remains;
ARM/QNN unvalidated without hardware.

# Future Work

HP Snapdragon validation → NPU numbers → ETW event-driven sampling →
on-device adaptation with real labels → reversible confirmed user-approved
actions behind the same safety engine.
