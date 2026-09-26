# FINAL PHASE 4 NPU REPORT — Snapdragon Hexagon validation
Date (UTC): 2026-09-26. Model unaltered. No process modified. No hardware,
firmware, BIOS, kernel, or driver modified. No NPU results invented.

# 1. Development Hardware
Dell Inspiron 15 / Intel Core i5-1334U / Windows 11 x64 / Python 3.14.7.
No Hexagon NPU. Intel laptop used strictly as dev/host (preparation +
orchestration). Isolated venv: `qai-hub 0.55.0`.

# 2. Model
`models/process_classifier.onnx` (1.9 KB, unchanged): MLP 11→16→8→4,
float32 `[batch,11]` → probabilities `[batch,4]` + label, opset 12/IR 10,
Gemm/Relu/Softmax/ArgMax. Classes PROTECTED/USER_IMPORTANT/FLEXIBLE/
DEFERRABLE. Full inspection: `docs/NPU_MODEL_INSPECTION.md`.

# 3. Qualcomm Toolchain (actually installed, current)
qai-hub 0.55.0. Verified commands: `configure`, `list-devices`,
`submit-compile-job` (`--model --device --compile_options
"--target_runtime onnx" --input_specs "{'features': (1, 11)}"`),
`submit-compile-and-link-jobs` (`models=`, `compile_options=`,
`embed_in_onnx=True`), `submit-link-job`, `submit-profile-job`,
`submit-inference-job` (per-input lists of numpy arrays). Client API
signatures verified in-venv. Compatibility finding: int64 `label`
requires `--truncate_64bit_io` (first compiles jpe7xj015/jpyo29e75 failed
with exactly this message; no retrain needed).

# 4. Target Device
Snapdragon X Elite CRD (sc8380xp, hexagon v73, abi aarch64-windows,
os:windows, format:compute, frameworks onnx+qnn) / Windows 11.

# 5. Compile Result
jp0m9yd0g SUCCESS (also jgzlye845 SUCCESS). Historical int64 failures
retained in `artifacts/npu_validation/job_history.json`.

# 6. Profile Result
jpxlrj1lp SUCCESS (repeat j5wlr67zp/jglyqmqe5 SUCCESS). All 10 executed
nodes: compute_unit NPU with NPU cycle counts.

# 7. Execution Provider
QNN compile/link path (target `.dlc`, 13.1 KB); on-device execution via
the QNN runtime. No provider string in payload; established via path +
compute units, stated as such.

# 8. Compute Unit
NPU (per-node evidence, all nodes).

# 9. NPU Inference
Job j5wlrew3p SUCCESS on Snapdragon X Elite CRD. 4 probes executed;
outputs in `artifacts/npu_validation/inference_result_npu.json`
(a prior attempt jglyqmnl5 FAILED on input shape (4,11) vs compiled (1,11);
fixed to per-row batches — history retained).

# 10. CPU Comparison
4/4 argmax agreement; max per-class probability difference 0.0015
(quantization-level; bits not identical, not required). Full table:
`docs/NPU_OUTPUT_COMPARISON.md`. CPU reference: load 13.06 ms,
single-row 0.024 ms.

# 11. Output Consistency
PASS (shapes [4]+label, class order identical, classes agree, diffs tiny).

# 12. Application Integration
Backend abstraction verified (13 phase-4 tests); app falls back and stays
functional on Dell (verified live). Dashboard renders HEXAGON NPU strings
only when detected (code path present; Dell shows CPU FALLBACK).

# 13. HP Validation
REQUIRES PHYSICAL HP SNAPDRAGON PC. Hosted CRD proves NPU execution,
never HP-branded hardware. Dashboard + endpoint state this explicitly.

# 14. Limitations (honest)
NPU profile/inference values are Hub-reported without API-defined units —
kept raw, never converted to ms. Full application was not executed on
Snapdragon hardware (model-level validation only). Token lives in
~/.qai_hub (outside repo); it passed through chat, so rotation is advised.
Early failed jobs retained as history, not hidden.

Status: **PHASE 4: FULLY NPU VALIDATED** (model-level; HP app validation
still requires hardware).
