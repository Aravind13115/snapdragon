# Snapdragon AI Smart Process & Task Manager

[![Hackathon Project](https://img.shields.io/badge/Hackathon-2026-blue.svg)](https://github.com/Aravind13115/snapdragon)
[![Platform](https://img.shields.io/badge/Platform-Windows%20on%20ARM-red.svg)](https://www.qualcomm.com/products/mobile/snapdragon/snapdragon-x-elite)
[![AI Engine](https://img.shields.io/badge/AI-ONNX%20%2B%20Hexagon%20NPU-green.svg)](https://github.com/Aravind13115/snapdragon)

**Technical name:** Snapdragon AI Adaptive Process Optimizer
**Positioning:** a stability-first, Snapdragon-aware AI resource-management
prototype for Snapdragon-powered HP Windows-on-Arm PCs.

> Designed and developed with the intent to be optimised for
> Snapdragon-powered HP PCs.

---

## Hackathon Submission

This project was built for a hackathon, showcasing AI-driven process optimization
leveraging Snapdragon X Elite's Hexagon NPU for on-device inference.

## 1. Problem
Background CPU workloads fight foreground applications for resources while
draining battery — worse on thin-and-light Windows on Arm machines where
native ARM64 and emulated x86/x64 workloads mix. Raw utilization graphs
can't say which background work is safe to defer, so nothing is deferred
or the wrong process is killed.

## 2. Solution
Observe → Understand → Predict → Protect → Recommend → Simulate: real
telemetry feeds an 11-signal feature engine and a 1.9 KB ONNX neural net;
calibrated confidence × OOD familiarity gates a deterministic safety layer;
only familiar high-confidence background work becomes an advisory
optimization candidate, demonstrated through non-destructive simulation.

## 3. Why AI
A single CPU threshold can't distinguish a foreground compile from an idle
sync client at 8%. Eleven contextual signals (trend, io, net, foreground,
battery, user activity, arch, emulation, history, protection) let the model
vote on workload *role*, while calibration keeps it honest about what it
hasn't seen.

## 4. Why Snapdragon
Neural inference is the product's hot loop, and it targets the Hexagon NPU:
standard ONNX → ONNX Runtime → Qualcomm QNN → Hexagon NPU, auto-selected
when present (CPU FALLBACK otherwise, explicitly reported). Verified: the
exact model compiled, profiled (all 10 nodes NPU), and executed on a
Snapdragon X Elite CRD via AI Hub — 4/4 outputs matching CPU. Local
inference keeps everything offline and private; Windows ML / ONNX Runtime
is the compatible deployment path.

## 5. Safety
Protected-process allowlist, foreground-window protection, confidence
floors (0.85/0.50), OOD unfamiliarity → PROTECT; model vote vs final
decision separate in code, API, UI, logs; STOP AI OPTIMIZATION disables
simulation server-side while monitoring continues; zero process-control
code paths (audited). Reversible by design: Phase 3+ actions exist only as
simulated projections.

## 6. Architecture
SNAPDRAGON HP PC → Windows 11 on ARM → telemetry (tiered sampler, ~1% CPU)
→ feature engine → lightweight ONNX neural network → Qualcomm QNN →
Hexagon NPU (CPU fallback on dev) → AI classification → confidence + OOD →
safety engine → optimization recommendation → safe simulation → dashboard.

## 7. AI Model
`11 → 16 → 8 → 4`, ONNX, **1.9 KB**, opset 12. Synthetic-trained (87.38%
synthetic fit — NOT real-world accuracy). T=2.0 temperature folded in.
Classes: PROTECTED / USER_IMPORTANT / FLEXIBLE / DEFERRABLE.

## 8. Validation
- Intel Dell: CPU FALLBACK VERIFIED (telemetry/AI/safety/simulation, 74/74 tests).
- Snapdragon X Elite CRD: compile jp0m9yd0g, link j568m6rng, profile
  jpxlrj1lp (all nodes NPU + cycles), inference j5wlrew3p — 4/4 argmax,
  max diff 0.0015. NPU values kept in Hub-reported units (unconverted).
- HP Snapdragon full application: REQUIRES physical HP hardware (CRD proves
  NPU execution, never HP).

## 9. Measurements (verified only)
Model 1.9 KB · CPU inference 0.024 ms/row · app ~1% steady CPU · ~70 MB RAM
· API <160 ms · simulator 0.002 ms/call · NPU profile+inference VERIFIED.
No battery-savings or optimization-savings claims (unmeasured).

## 10. Limitations
Synthetic training data; real-world classification precision not
established; full application not tested on HP Snapdragon hardware;
projected simulation values are not benchmark results; local Intel machine
uses CPU fallback; ~1% polling overhead; dashboard verified via headless DOM.

## 11. Demo
```powershell
cd C:\Users\ariko\OneDrive\Desktop\snapdragon
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:8099/
```
START DEMO (presenting) → SIMULATE → history → STOP toggle → scenarios
(sync/active/uncertain/critical). Script: `presentation/demo_script.md`.
Evidence: `logs/ai_decisions.jsonl`, `artifacts/npu_validation/`,
screenshots `presentation/dashboard*.png`.

---
*Reports: FINAL_FREEZE.md · FINAL_COMPETITION_PACKAGE.md ·
FINAL_PHASE4_NPU_REPORT.md · PHASE3_REPORT.md · PHASE2.7_REPORT.md*
