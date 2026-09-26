# 03 — Architecture
SNAPDRAGON HP PC → Windows 11 on ARM → telemetry (tiered sampler) →
feature engine (11 signals) → ONNX MLP 11→16→8→4 → QNN/Hexagon NPU
(CPU fallback on dev) → temperature calibration + OOD familiarity →
safety engine → recommendation → non-destructive simulation → dashboard.
Order: STABILITY → SAFETY → CORRECTNESS → AI → NPU → OPTIMIZATION.
