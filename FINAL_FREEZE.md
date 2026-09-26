# FINAL FREEZE — competition submission baseline
Date (UTC): 2026-09-26. No further core changes after this point without a
critical blocking defect.

- App version: 0.3.0-phase3+ (config.py)
- Model: models/process_classifier.onnx v0.2.5-phase2.5 (MLP 11→16→8→4,
  1.9 KB, opset 12) — FROZEN (no retrain)
- Feature schema: 11 signals, ai/dataset.py FEATURES — FROZEN
- Calibration T=2.0, OOD RBF (d_ref 2.58), thresholds 0.85/0.50 — FROZEN
- Safety engine + simulator + backend abstraction — FROZEN
- Tests: 74 total (10+10+10+11+13+20), all passing at freeze
- Qualcomm jobs (final): compile jp0m9yd0g + jgzlye845 SUCCESS;
  link j568m6rng SUCCESS; profile jpxlrj1lp SUCCESS (all nodes NPU);
  inference j5wlrew3p SUCCESS (4/4 argmax, max diff 0.0015).
  Early failures (int64 flag, batch shape) retained as documented history.
- Git: not a git repository (plain project directory); baseline = this tree.
- Limitations (frozen with the code): synthetic training; live skews
  PROTECT/REVIEW; best-effort disk/net; illustrative projections; full app
  never ran on Snapdragon hardware; HP validation requires HP hardware;
  ~1% polling overhead.
