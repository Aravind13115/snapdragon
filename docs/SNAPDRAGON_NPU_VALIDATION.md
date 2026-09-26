# SNAPDRAGON NPU VALIDATION (Phase 4 — executed results)

> The prototype does not modify Snapdragon silicon, NPU firmware, CPU
> firmware, or Windows kernel behavior. The existing Snapdragon Hexagon NPU
> is used as an execution target through Qualcomm's supported
> software/runtime stack.

## Development Environment
Dell Inspiron 15 / Intel Core i5 / Windows 11 x64 / Python 3.14.7.
No Hexagon NPU present. Isolated venv with `qai-hub 0.55.0`, authenticated
(token in ~/.qai_hub only, never in repo).

## Model
`models/process_classifier.onnx` (1.9 KB, unaltered): input float32
`[batch, 11]`, outputs probabilities `[batch, 4]` + label, opset 12 /
IR 10, ops Gemm/Relu/Softmax/ArgMax. Full inspection:
`docs/NPU_MODEL_INSPECTION.md`.

## Snapdragon Target
Snapdragon X Elite CRD (sc8380xp, hexagon v73, Windows 11, Compute) —
authenticated device list, Android/mobile excluded.

## Qualcomm AI Hub Jobs (all verified live, history retained)
- Compile jp0m9yd0g SUCCESS (jgzlye845 SUCCESS; early jpe7xj015/jpyo29e75
  FAILED on int64 label → fixed with `--truncate_64bit_io`, no retrain)
- Link j568m6rng SUCCESS (target `.dlc` 13.1 KB)
- Profile jpxlrj1lp SUCCESS — all 10 nodes compute_unit NPU + cycle counts
- Inference j5wlrew3p SUCCESS (prior jglyqmnl5 FAILED on (4,11) vs (1,11);
  fixed to per-row batches). 4 probes executed on-device.

## Runtime
QNN compile/link path; on-device execution via QNN runtime on the
hosted target. Local ORT providers remain [Azure, CPU].

## Compute Unit
NPU (per-node profile evidence, all executed nodes).

## Inference
4/4 argmax agreement vs CPU; max prob diff 0.0015. Outputs:
`artifacts/npu_validation/inference_result_npu.json`. Comparison:
`docs/NPU_OUTPUT_COMPARISON.md`.

## CPU Comparison
CPU: load 13.06 ms, single-row 0.024 ms. NPU profile values kept in
Hub-reported units (see `docs/SNAPDRAGON_NPU_BENCHMARK.md`).

## Validation Status
- LOCAL CPU: VERIFIED
- SNAPDRAGON NPU (model-level): VERIFIED (profile + inference)
- Allowed claim: "The ONNX process-classification model was validated for
  execution on a Snapdragon X Elite Windows target through Qualcomm's
  AI Hub/QNN NPU path."

## HP Hardware Status
HP-specific full-application validation: REQUIRES PHYSICAL HP SNAPDRAGON PC.
Hosted CRD proves NPU execution, never HP-branded hardware.

## Limitations
Hub-reported times lack API-defined units (kept raw). Full app never ran
on Snapdragon hardware. Token passed through chat — rotation advised.
