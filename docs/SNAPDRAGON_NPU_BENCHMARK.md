# NPU Benchmark — process_classifier.onnx (REAL measurements only)

## CPU (Dell Inspiron 15, Intel i5-1334U, ONNX Runtime 1.30.0) — VERIFIED
- Model load: 13.06 ms
- Single row: 0.024 ms
- Batch64: 0.051 ms (0.0008 ms/row)
- Source: `python -m inference.bench` (this machine, 2026-09-26)

## Snapdragon NPU — MEASURED via Qualcomm AI Hub profile job jpxlrj1lp
- Model: process_classifier.onnx (unaltered, `--target_runtime onnx`,
  `--truncate_64bit_io`, input `features: (1, 11)`)
- Target: Snapdragon X Elite CRD (sc8380xp, hexagon v73, Windows 11)
- Runtime: QNN (target artifact: compiled `.dlc`, 13.1 KB)
- Compute unit: **NPU** — all 10 profiled nodes (Input, 7 graph nodes +
  identity, Output) report `compute_unit: NPU` with NPU cycle counts
- Profile execution_summary (Hub-reported values, original units retained —
  Qualcomm does not label them ms, so no conversion is made):
  estimated_inference_time 145 · first_load_time 540811 ·
  warm_load_time 267086 · inference peak memory 655360 B ·
  warm-load peak memory 14770176 B · measured inference samples cluster
  145–197 (first 1252).
- NPU inference job j5wlrew3p (SUCCESS): 4 probe vectors executed on-device;
  outputs in `artifacts/npu_validation/inference_result_npu.json`;
  comparison in `docs/NPU_OUTPUT_COMPARISON.md` (4/4 argmax, max diff 0.0015).
- Artifact: `artifacts/npu_validation/profile_result.json`

## How the NPU row was produced
compile job jp0m9yd0g → link jgly8jn85 → profile jpxlrj1lp
(`tools/npu_hub_run.py`). No values estimated; no other model's numbers.
