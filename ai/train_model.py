"""Train the prototype workload classifier and export to ONNX.

Pipeline:
    prototype_synthetic_process_dataset (ai/dataset.py)
      -> StandardScaler normalization (folded into the ONNX graph, so the
         .onnx file accepts RAW features in the documented order)
      -> MLP (12 -> 16 -> 8 -> 4, ReLU, softmax) trained with Adam
      -> accuracy evaluation
      -> ONNX export (models/process_classifier.onnx)
      -> metadata (models/model_metadata.json)

Implementation note: pure NumPy training + hand-built ONNX graph.
sklearn/scipy native DLLs are blocked by Application Control policy on
some dev machines, and a hand-built graph keeps the model minimal and
NPU-friendly (Gemm/Relu/Softmax/ArgMax only).

Usage:
    python ai/train_model.py

Training-time imports: numpy, onnx.
Runtime imports: numpy, onnxruntime.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.dataset import (CLASS_NAMES, DATASET_NAME, FEATURES, N_FEATURES,  # noqa: E402
                        generate)

MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "process_classifier.onnx"
META_PATH = MODEL_DIR / "model_metadata.json"

MODEL_VERSION = "0.2.5-phase2.5"
CONFIDENCE_THRESHOLD = 0.85
OOD_FAMILIARITY_THRESHOLD = 0.35


# ---------------------------------------------------------------- MLP ----

def _relu(z):
    return np.maximum(z, 0.0)


def _softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def train_mlp(Xtr, ytr, Xte, yte, seed=7):
    rng = np.random.default_rng(seed)
    n, d = Xtr.shape
    ncls = 4
    h1, h2 = 16, 8
    W1 = rng.normal(0, np.sqrt(2 / d), (d, h1)).astype(np.float64)
    b1 = np.zeros(h1)
    W2 = rng.normal(0, np.sqrt(2 / h1), (h1, h2)).astype(np.float64)
    b2 = np.zeros(h2)
    W3 = rng.normal(0, np.sqrt(2 / h2), (h2, ncls)).astype(np.float64)
    b3 = np.zeros(ncls)
    Y1 = np.eye(ncls)[ytr]

    lr, epochs, bs = 0.02, 250, 64
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    m = [np.zeros_like(p) for p in (W1, b1, W2, b2, W3, b3)]
    v = [np.zeros_like(p) for p in (W1, b1, W2, b2, W3, b3)]

    def forward(X):
        z1 = X @ W1 + b1
        a1 = _relu(z1)
        z2 = a1 @ W2 + b2
        a2 = _relu(z2)
        z3 = a2 @ W3 + b3
        return z1, a1, z2, a2, z3, _softmax(z3)

    t = 0
    for ep in range(epochs):
        perm = rng.permutation(n)
        for s in range(0, n, bs):
            t += 1
            xb = Xtr[perm[s:s + bs]]
            yb = Y1[perm[s:s + bs]]
            mb = len(xb)
            z1, a1, z2, a2, _, p = forward(xb)
            dz3 = (p - yb) / mb
            dW3, db3 = a2.T @ dz3, dz3.sum(0)
            da2 = dz3 @ W3.T
            dz2 = da2 * (z2 > 0)
            dW2, db2 = a1.T @ dz2, dz2.sum(0)
            da1 = dz2 @ W2.T
            dz1 = da1 * (z1 > 0)
            dW1, db1 = xb.T @ dz1, dz1.sum(0)
            for i, g in enumerate((dW1, db1, dW2, db2, dW3, db3)):
                m[i] = beta1 * m[i] + (1 - beta1) * g
                v[i] = beta2 * v[i] + (1 - beta2) * g * g
                mh = m[i] / (1 - beta1 ** t)
                vh = v[i] / (1 - beta2 ** t)
                upd = lr * mh / (np.sqrt(vh) + eps)
                if i == 0:
                    W1 -= upd
                elif i == 1:
                    b1 -= upd
                elif i == 2:
                    W2 -= upd
                elif i == 3:
                    b2 -= upd
                elif i == 4:
                    W3 -= upd
                else:
                    b3 -= upd
    _, _, _, _, ztr, ptr = forward(Xtr)
    _, _, _, _, zte, pte = forward(Xte)
    return ((ptr.argmax(1) == ytr).mean(), (pte.argmax(1) == yte).mean(),
            (W1, b1, W2, b2, W3, b3), zte)


# --------------------------------------------------------------- ONNX ----

def export_onnx(W1, b1, W2, b2, W3, b3, mean, scale, temperature=1.0):
    """Build Gemm/Relu/Softmax/ArgMax graph; fold scaler into first layer
    and temperature scaling into the last layer (W3/T, b3/T), so ORT
    outputs calibrated probabilities directly."""
    import onnx
    from onnx import TensorProto, helper

    W1f = (W1 / scale[:, None]).astype(np.float32)
    b1f = (b1 - (mean / scale) @ W1).astype(np.float32)
    W2 = W2.astype(np.float32)
    b2 = b2.astype(np.float32)
    W3 = (W3 / temperature).astype(np.float32)
    b3 = (b3 / temperature).astype(np.float32)

    def init(name, arr):
        return helper.make_tensor(name, TensorProto.FLOAT, arr.shape,
                                  arr.ravel().tolist())

    X = helper.make_tensor_value_info("features", TensorProto.FLOAT, ["batch", N_FEATURES])
    P = helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, ["batch", 4])
    L = helper.make_tensor_value_info("label", TensorProto.INT64, ["batch"])

    nodes = [
        helper.make_node("Gemm", ["features", "W1", "b1"], ["z1"]),
        helper.make_node("Relu", ["z1"], ["a1"]),
        helper.make_node("Gemm", ["a1", "W2", "b2"], ["z2"]),
        helper.make_node("Relu", ["z2"], ["a2"]),
        helper.make_node("Gemm", ["a2", "W3", "b3"], ["logits"]),
        helper.make_node("Softmax", ["logits"], ["probabilities"], axis=1),
        helper.make_node("ArgMax", ["probabilities"], ["label"], axis=1,
                         keepdims=0),
    ]
    graph = helper.make_graph(
        nodes, "process_priority_mlp",
        [X], [P, L],
        [init("W1", W1f), init("b1", b1f), init("W2", W2),
         init("b2", b2), init("W3", W3), init("b3", b3)])
    model = helper.make_model(graph, producer_name="snapdragon-prototype-phase2")
    model.opset_import[0].version = 12
    model.ir_version = 10  # onnxruntime compat (newer onnx emits IR the ORT build can't read)
    onnx.checker.check_model(model)
    return model


# ---------------------------------------------------------------- main ----

def main() -> dict:
    t0 = time.time()
    X, y = generate(n_per_class=1000, seed=42)
    # Deterministic stratified-ish split: dataset is pre-shuffled.
    Xte, yte = X[:800], y[:800]
    Xtr, ytr = X[800:], y[800:]

    mean = Xtr.mean(axis=0)
    scale = Xtr.std(axis=0) + 1e-9
    Xtr_s = ((Xtr - mean) / scale)
    Xte_s = ((Xte - mean) / scale)

    train_acc, test_acc, (W1, b1, W2, b2, W3, b3), zte = train_mlp(
        Xtr_s, ytr, Xte_s, yte)
    train_s = round(time.time() - t0, 1)

    # --- temperature scaling (fit on held-out test logits, NLL grid) ---
    def nll(T):
        e = np.exp((zte - zte.max(1, keepdims=True)) / T)
        p = e / e.sum(1, keepdims=True)
        return float(-np.log(p[np.arange(len(yte)), yte] + 1e-12).mean())

    best_T, best_nll = 1.0, nll(1.0)
    for T in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0):
        v = nll(T)
        if v < best_nll:
            best_T, best_nll = T, v

    # --- OOD reference: per-class centroids in standardized space ------
    centroids = []
    for c in range(4):
        centroids.append(Xtr_s[ytr == c].mean(axis=0))
    centroids = np.stack(centroids)
    # Reference distance: median train distance to own centroid (RBF bandwidth).
    d_all = np.min(
        np.stack([np.linalg.norm(Xtr_s - c, axis=1) for c in centroids]),
        axis=0)
    d_ref = float(np.median(d_all))

    model = export_onnx(W1, b1, W2, b2, W3, b3, mean, scale,
                        temperature=best_T)
    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        f.write(model.SerializeToString())
    size_kb = round(MODEL_PATH.stat().st_size / 1024, 1)

    meta = {
        "model_name": "process_priority_classifier",
        "version": MODEL_VERSION,
        "dataset": DATASET_NAME,
        "dataset_version": "v2-diverse-noprotectflag",
        "training": "prototype-synthetic",
        "warning": ("PROTOTYPE ONLY: trained on synthetic data for a competition "
                    "demo. Not production training data. Synthetic test accuracy "
                    "does NOT transfer to real telemetry. Do not use for real "
                    "process-management decisions."),
        "implementation": "numpy-MLP, hand-built ONNX graph (Gemm/Relu/Softmax/"
                          "ArgMax; scaler folded into layer 1, temperature "
                          "folded into layer 3)",
        "architecture": {"type": "MLP", "layers": [N_FEATURES, 16, 8, 4],
                         "activation": "relu", "optimizer": "adam"},
        "features": FEATURES,
        "classes": CLASS_NAMES,
        "normalization": {"type": "standard-scaler folded into ONNX graph",
                          "mean": [float(v) for v in mean],
                          "scale": [float(v) for v in scale]},
        "calibration": {"method": "temperature-scaling (NLL grid on held-out "
                                  "synthetic test set)",
                        "temperature": best_T,
                        "nll_at_T": round(best_nll, 4)},
        "ood_reference": {
            "method": "nearest class centroid in standardized feature space; "
                      "familiarity = exp(-0.5*(d/d_ref)^2), d_ref = median "
                      "training distance",
            "centroids": [[float(v) for v in row] for row in centroids],
            "d_ref": d_ref,
            "familiarity": "RBF kernel on centroid distance; extreme |z|>5 halves it",
            "ood_threshold": OOD_FAMILIARITY_THRESHOLD,
        },
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "train_accuracy": round(float(train_acc), 4),
        "test_accuracy": round(float(test_acc), 4),
        "test_samples": int(len(yte)),
        "train_samples": int(len(ytr)),
        "train_seconds": train_s,
        "model_file": "models/process_classifier.onnx",
        "model_size_kb": size_kb,
        "opset": 12,
    }
    META_PATH.write_text(json.dumps(meta, indent=2))

    print("feature order:")
    for i, name in enumerate(FEATURES):
        print(f"  [{i}] {name}")
    print(f"classes: {CLASS_NAMES}")
    print(f"train acc: {train_acc:.4f} | test acc: {test_acc:.4f} "
          f"({len(yte)} test samples)")
    print(f"model: {MODEL_PATH} ({size_kb} KB, opset 12)")
    print(f"metadata: {META_PATH}")
    print(f"confidence threshold: {CONFIDENCE_THRESHOLD}")
    return meta


if __name__ == "__main__":
    main()
