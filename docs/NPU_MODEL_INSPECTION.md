# NPU Model Inspection — process_classifier.onnx (unaltered Phase-2.5 model)

Inspected 2026-09-26 directly from `models/process_classifier.onnx`
(model NOT retrained for Phase 4).

## Identity
- File: `models/process_classifier.onnx` (1.9 KB)
- Producer: snapdragon-prototype-phase2 (hand-built NumPy graph)
- Metadata: `models/model_metadata.json`, version 0.2.5-phase2.5

## Graph
- IR version: 10 · Opset: ai.onnx v12
- Input: `features`, tensor(float32) `[batch, 11]` (batch dynamic)
- Outputs: `probabilities` float32 `[batch, 4]`, `label` int64 `[batch]`
- Nodes: Gemm ×3, Relu ×2, Softmax ×1 (axis=1), ArgMax ×1 (axis=1)
- Data type: FLOAT (elem type 1) throughout

## Preprocessing (folded into the graph — host sends RAW features)
- Standard-scaler folded into layer 1 (mean/scale in metadata `normalization`)
- Temperature T=2.0 folded into layer 3 (metadata `calibration`)
- Host contract: 11 raw floats in documented order, no quantization needed
  for the CPU path; QNN conversion handles quantization at compile time.

## Feature order (must match ai/dataset.py FEATURES)
0 cpu_norm · 1 cpu_trend · 2 mem_norm · 3 io_rate · 4 net_level ·
5 is_foreground · 6 on_battery · 7 user_activity · 8 arch_native ·
9 is_emulated · 10 hist_cpu

## Class ordering (output index = class id)
0 PROTECTED · 1 USER_IMPORTANT · 2 FLEXIBLE · 3 DEFERRABLE

## QNN suitability notes
- Only standard dense/activation/reduction ops (Gemm/Relu/Softmax/ArgMax):
  no control flow, no custom ops, dynamic batch dim only.
- Softmax+ArgMax tail is classically supported; if the QNN converter
  prefers logits, the ArgMax/Softmax nodes are droppable (logits = Gemm#3
  output) — documented fallback, not yet needed.
- COMPATIBILITY FINDING (Hub compile, verified): the int64 `label` output
  (ArgMax default) requires compile flag `--truncate_64bit_io`, which
  converts it to int32 at compile time. No retrain needed; the app reads
  labels via `int()`, dtype-agnostic. First compile without the flag
  failed with exactly this message (job jpyo29e75).
- No retraining performed: compatibility is tested as-is first.
