# Snapdragon NPU Validation Guide (Phase 4)
Target: Snapdragon-powered HP PC, Windows 11 on ARM (Snapdragon X Elite/X Plus).

## Deployment chain (software onto existing silicon)

> The neural-network model is deployed to and executed by the existing
> Snapdragon Hexagon NPU through the Qualcomm software/runtime stack.
> Nothing here modifies silicon, firmware, microcode, drivers, or kernel.

```text
models/process_classifier.onnx (MLP 11→16→8→4, opset 12, Gemm/Relu/Softmax/ArgMax)
  → ONNX Runtime with QNNExecutionProvider (Windows ML compatible)
  → Qualcomm QNN SDK
  → Snapdragon Hexagon NPU (local inference)
```

The model uses only standard ONNX ops supported by the QNN EP. The app's
`inference/backend.py::select()` picks `HEXAGON NPU` automatically when
`qnn_backend.probe()` reports a Snapdragon ARM host AND onnxruntime
exposes `QNNExecutionProvider`; otherwise it stays on CPU FALLBACK.
No code change is needed on the HP machine beyond installing a QNN-enabled
ONNX Runtime build + Qualcomm QNN SDK.

## Validation procedure (on the HP Snapdragon PC)

```powershell
cd <project>
pip install -r requirements.txt      # + QNN-enabled onnxruntime build
python -m inference.bench            # CPU numbers + NPU scaffold status
python tests/test_phase4.py          # backend/selection/truthfulness tests
python app.py                        # dashboard: expect Execution Provider QNN,
                                     # NPU: AVAILABLE, backend HEXAGON NPU
python ai/analyze.py                 # live classification distribution
```

Record: provider list, NPU latency (single + batch64), model load time,
CPU utilization during NPU inference, output equality vs CPU backend
(argmax agreement on a fixed probe set), dashboard backend strings.

## Current status (Intel dev machine, verified)

QNN UNAVAILABLE · NPU UNAVAILABLE · CPU FALLBACK — correct, not a failure.
All NPU performance fields in `inference/bench.py` return
`REQUIRES_SNAPDRAGON_HARDWARE`. The dashboard never claims NPU ACTIVE here.
