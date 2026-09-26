"""Out-of-distribution detection: is this live vector familiar?

Method (prototype-simple, deterministic):
  * Training-time per-class centroids in STANDARDIZED feature space are
    stored in models/model_metadata.json (ood_reference.centroids),
    along with the scaler mean/scale and d_ref (median training distance).
  * For a live RAW vector: standardize with the SAME mean/scale, take the
    Euclidean distance to the nearest centroid and apply an RBF kernel:
        familiarity = exp(-0.5 * (d_min / d_ref)^2)   in (0, 1]
    * any |z_i| > 5 (wildly outside every training marginal) halves it.
  * familiarity < threshold (0.35) => OOD => safety layer forces PROTECT.

The model is allowed to be wrong; unfamiliarity is a reason to protect.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
META_PATH = ROOT / "models" / "model_metadata.json"

OOD_THRESHOLD = 0.35

_mean: np.ndarray | None = None
_scale: np.ndarray | None = None
_centroids: np.ndarray | None = None
_d_ref: float = 2.6


def _load():
    global _mean, _scale, _centroids
    if _mean is not None:
        return
    meta = json.loads(META_PATH.read_text())
    _mean = np.asarray(meta["normalization"]["mean"], dtype=float)
    _scale = np.asarray(meta["normalization"]["scale"], dtype=float)
    _centroids = np.asarray(meta["ood_reference"]["centroids"], dtype=float)
    global _d_ref
    _d_ref = float(meta["ood_reference"].get("d_ref", 2.6))
    set_threshold(float(meta["ood_reference"].get("ood_threshold", 0.35)))


def set_threshold(v: float):
    global OOD_THRESHOLD
    OOD_THRESHOLD = v


def standardize(vec) -> np.ndarray:
    """Identical normalization to training. Shared by OOD + validation."""
    _load()
    return (np.asarray(vec, dtype=float) - _mean) / _scale


def familiarity(vec) -> dict:
    """Returns {familiarity, distance, ood, level}."""
    _load()
    z = standardize(vec)
    d = min(float(np.linalg.norm(z - c)) for c in _centroids)
    fam = float(np.exp(-0.5 * (d / _d_ref) ** 2))
    extreme = bool((np.abs(z) > 5.0).any())
    if extreme:
        fam *= 0.5
    ood = fam < OOD_THRESHOLD
    level = "HIGH" if fam >= 0.6 else ("MEDIUM" if fam >= OOD_THRESHOLD else "LOW")
    if ood:
        level = "UNKNOWN"
    return {"familiarity": round(fam, 4), "distance": round(d, 3),
            "ood": ood, "level": level, "extreme_feature": extreme}
