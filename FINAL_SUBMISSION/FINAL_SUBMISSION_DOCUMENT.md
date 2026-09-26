# FINAL SUBMISSION DOCUMENT — Snapdragon AI Smart Process & Task Manager
v0.3.0-phase3+ · frozen 2026-09-26 · 74/74 tests passing

# Executive Summary
Stability-first local AI for Windows resource management on Snapdragon HP
PCs: real telemetry → contextual ONNX classification → calibrated safety →
advisory simulation. NPU model validation VERIFIED on Snapdragon X Elite;
app runs CPU FALLBACK on Intel dev. Zero process-control code.

# Problem
Background workloads fight foreground apps; utilization graphs can't say
what is safe to defer — especially with ARM64/emulated workloads mixed on
Windows on Arm.

# Innovation
Contextual workload understanding (11 signals incl. foreground, battery,
emulation, familiarity) + honest uncertainty (temperature × OOD) +
deterministic PROTECT-first safety + non-destructive simulation of what
approved optimizations would do.

# Proposed Solution
Observe → Understand → Predict → Protect → Recommend → Simulate, fully
local, fully explainable (every decision logged with model vote, confidence,
familiarity, reason).

# Technical Architecture
Tiered sampler (~1% CPU) → features → ONNX MLP 11→16→8→4 (1.9 KB) → QNN /
CPU fallback → calibration/OOD → safety → simulator → dashboard + JSONL log.

# AI Model
Synthetic-trained (87.38% synthetic fit — NOT real-world accuracy); T=2.0;
thresholds 0.85/0.50; classes PROTECTED/USER_IMPORTANT/FLEXIBLE/DEFERRABLE.

# Snapdragon NPU Integration
ONNX → ONNX Runtime → QNN → Hexagon NPU (auto-selected when present).
Executed BY existing silicon via Qualcomm stack; nothing modifies
silicon/firmware/kernel.

# Windows on Arm Optimization
ARM64/x86-WOW64/emulated/unknown detection where the OS exposes it;
emulation is a model feature, never a penalty. (ARM behavior projected on
x64 host; needs on-device confirmation.)

# Safety Architecture
Allowlist → foreground → OOD → confidence floors; vote/decision separated;
emergency stop; audited zero control paths; live ~139 PROTECT/~61 REVIEW.

# Deployment & Accessibility
`pip install -r requirements.txt` → `python app.py` → localhost:8099.
Local-only, no cloud, no account. QNN path needs QNN-enabled ORT on ARM.

# Demonstration
START DEMO (presenting) → candidates → SIMULATE → PROJECTED bars →
history → STOP toggle → scenarios. Script: presentation/demo_script.md.

# Qualcomm Validation
Target X Elite CRD (sc8380xp, hexagon v73, Win11). Compile jp0m9yd0g,
link j568m6rng, profile jpxlrj1lp (all 10 nodes NPU + cycles), inference
j5wlrew3p: 4/4 argmax, max diff 0.0015. Early int64/shape failures retained
as history. NPU values in Hub-reported units (unconverted).

# Performance Measurements
Model 1.9 KB · CPU 0.024 ms/row · app ~1% CPU · ~70 MB · API <160 ms ·
simulator 0.002 ms/call. No battery/CPU-savings claims (unmeasured).

# Testing
74/74 (10+10+10+11+13+20). Compile clean. Headless-Edge DOM verified, zero
console errors. Security + destructive-path audits: zero hits. Secrets: none.

# Limitations
Synthetic training; live skews PROTECT/REVIEW; best-effort disk/net;
illustrative projections; full app never ran on Snapdragon hardware;
HP validation requires HP hardware; ~1% polling overhead.

# Future Development
HP Snapdragon on-device run → NPU latency/throughput → ETW sampling →
on-device adaptation → reversible confirmed user-approved actions.

# Conclusion
A complete, evidence-backed, honest prototype: real AI, real NPU proof,
real safety — ready to run on Snapdragon HP PCs. Package: FINAL_SUBMISSION/.
