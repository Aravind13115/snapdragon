# NPU Output Comparison — CPU reference vs Snapdragon NPU (pending)

## CPU reference (Dell, CPUExecutionProvider — VERIFIED 2026-09-26)

| Probe | Label | Probabilities [P,U,F,D] | Confidence |
|---|---|---|---|
| protected | PROTECTED | [0.8387, 0.0000, 0.0147, 0.1465] | 0.8387 |
| foreground | USER_IMPORTANT | [0.0000, 1.0000, 0.0000, 0.0000] | 1.0000 |
| flexible | FLEXIBLE | [0.0000, 0.0191, 0.9809, 0.0000] | 0.9809 |
| deferrable | DEFERRABLE | [0.0009, 0.0000, 0.0051, 0.9940] | 0.9940 |

Source: `artifacts/npu_validation/inference_result.json` (harness probes).

## NPU side (Snapdragon X Elite CRD, QNN, inference job j5wlrew3p SUCCESS)

| Probe | Label | Probabilities [P,U,F,D] | CPU argmax agree | Max prob diff |
|---|---|---|---|---|
| protected | 0 PROTECTED | [0.837891, 0.000046, 0.014702, 0.146240] | ✅ | 0.0008 |
| foreground | 1 USER_IMPORTANT | [0.000000, 0.998535, 0.000000, 0.000000] | ✅ | 0.0015 |
| flexible | 2 FLEXIBLE | [0.000000, 0.019180, 0.979981, 0.000001] | ✅ | 0.0009 |
| deferrable | 3 DEFERRABLE | [0.000860, 0.000040, 0.005070, 0.992676] | ✅ | 0.0013 |

## Acceptance result: PASS

- Argmax agreement 4/4 across the 4 probes.
- Max per-class probability difference 0.0015 (quantization-level;
  bit-identical floats not required, and not observed).
- Output shapes [4] + label scalar confirmed on-device.
- Artifact: `artifacts/npu_validation/inference_result_npu.json`.
