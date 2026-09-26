# FINAL COMPETITION PACKAGE — Snapdragon AI Smart Process Manager
Technical name: Snapdragon AI Adaptive Process Optimizer · v0.3.0-phase3+
Status: COMPETITION READY. No process modified/terminated/suspended at any stage.

# Product Overview
Stability-first local AI for Windows resource management on Snapdragon HP PCs.

# Problem
Background workloads compete with foreground apps; raw dashboards can't say
what is safe to defer.

# Innovation
Contextual AI (foreground/battery/emulation/familiarity) + calibrated
confidence + OOD gating + deterministic PROTECT-first safety + advisory
simulation — all local, all explainable.

# Architecture
Telemetry (tiered, ~1% CPU) → 11 features → ONNX MLP 11→16→8→4 (1.9 KB) →
QNN/Hexagon NPU (CPU fallback on dev) → T=2.0 calibration × RBF familiarity →
safety engine → recommendation → simulation → dashboard + decision log.

# AI Model
Synthetic-trained (87.38% synthetic fit — NOT real-world accuracy);
thresholds 0.85/0.50; classes PROTECTED/USER_IMPORTANT/FLEXIBLE/DEFERRABLE.

# Snapdragon NPU Architecture
ONNX → ONNX Runtime → QNN → Hexagon NPU (auto-selected when present).
Model executed BY existing silicon via Qualcomm stack; nothing modifies
silicon/firmware/kernel.

# Safety
Allowlist → foreground → OOD → confidence floors; vote vs decision separate;
emergency stop; zero process-control code (audited).

# Prototype Demonstration
START DEMO (presenting) → PowerPoint PROTECTED → sync/indexer candidates →
SIMULATE → PROJECTED bars → history → STOP toggle → scenarios. 3 minutes.
Real screenshot: presentation/dashboard.png.

# Measurements (verified, Intel)
Model 1.9 KB · CPU inference 0.024 ms/row · app ~1% CPU · ~70 MB RAM ·
API <160 ms · simulator 0.002 ms/call. NPU: profile + inference VERIFIED
(values in Hub units, unconverted). No battery/CPU-savings claims.

# Qualcomm Validation Evidence
Target Snapdragon X Elite CRD (sc8380xp, hexagon v73, Windows 11).
Compile jp0m9yd0g + jgzlye845 SUCCESS · link j568m6rng SUCCESS ·
profile jpxlrj1lp SUCCESS (all 10 nodes NPU + cycles) · inference j5wlrew3p
SUCCESS · CPU vs NPU 4/4 argmax, max diff 0.0015. Early int64/shape
failures retained as history. Artifacts: artifacts/npu_validation/.

# Testing
phase2 10 · phase25 10 · phase27 10 · phase3 11 · phase4 13 · integration 20
= 74 passed, 0 failed (one transient fg-sampling flake observed and
re-passed; rule covered deterministically in unit suites). Compile clean.
Headless-Edge DOM: all cards, zero console errors. Security/destructive
audit: zero hits. Secrets scan: zero hits.

# Security
Localhost-only, GET-only API, no uploads, no remote control, no registry/
driver/firmware writes, no process control, no stored credentials
(verified by scan).

# Limitations
Synthetic training; live skews PROTECT/REVIEW; best-effort disk/net;
illustrative projections; full app never ran on Snapdragon hardware;
~1% polling overhead; headless-DOM (not screenshot-interaction) verification.

# HP Validation Status
REQUIRES PHYSICAL HP SNAPDRAGON PC. Hosted CRD proves NPU execution only.

# How to Run
pip install -r requirements.txt → python app.py → http://127.0.0.1:8099/
→ tests/test_*.py → python ai/analyze.py → python -m inference.bench

# Competition Demo Flow
See presentation/07_demo.md + dashboard START DEMO. Evidence: logs/,
artifacts/, docs/, presentation/dashboard.png.
