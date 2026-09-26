"""Rule-based safety layer (Phase 2.5): prediction -> decision.

Architecture:
    Telemetry -> Neural Network -> Prediction (+calibrated confidence, OOD)
      -> Safety Rules -> Final Recommendation

The model predicts workload behavior. It has NO authority. The safety
layer independently enforces, in order:

    protected allowlist -> PROTECT
    kernel pseudo-process -> PROTECT
    foreground window owner -> PROTECT
    OOD / unfamiliar -> PROTECT
    final_confidence < 0.50 -> PROTECT
    final_confidence < 0.85 -> REVIEW
    else -> PROTECT (PROTECTED) / OBSERVE (USER_IMPORTANT) /
            OPTIMIZATION CANDIDATE (FLEXIBLE, DEFERRABLE)

final_confidence = calibrated_model_confidence x familiarity  (conservative)

Safety states in Phase 2.5: PROTECT | OBSERVE | REVIEW |
OPTIMIZATION CANDIDATE. There is no OPTIMIZE NOW; everything is
recommendation text only and no code path modifies any process.
"""
from __future__ import annotations

from ai import ood as _ood
from safety.allowlist import is_protected

THRESHOLD = 0.85
REVIEW_FLOOR = 0.50

CLASSES = ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"]

_STATE_REC = {
    "PROTECTED": ("PROTECT", "PROTECT"),
    "USER_IMPORTANT": ("OBSERVE", "PROTECT"),  # user work: watch, never disturb
    "FLEXIBLE": ("OPTIMIZATION CANDIDATE", "REDUCE BACKGROUND ACTIVITY"),
    "DEFERRABLE": ("OPTIMIZATION CANDIDATE", "DEFER WHEN APPROPRIATE"),
}


def finalize(name: str, class_id: int, calibrated_conf: float,
             vec, *, is_foreground: bool = False,
             kernel_pseudo: bool = False) -> dict:
    """Combine model output + OOD + rules into a final safety decision."""
    model_class = CLASSES[class_id] if 0 <= class_id < 4 else "DEFERRABLE"
    fam = _ood.familiarity(vec)
    final = round(float(calibrated_conf) * fam["familiarity"], 4)

    base = {"model_class": model_class,
            "raw_confidence": round(float(calibrated_conf), 4),
            "familiarity": fam["familiarity"],
            "familiarity_level": fam["level"],
            "ood": fam["ood"],
            "distance": fam["distance"],
            "final_confidence": final,
            "simulated": False}

    def protect(reason):
        return base | {"ai_class": "PROTECTED", "safety_state": "PROTECT",
                       "recommendation": "PROTECT", "high_confidence": False,
                       "overridden": True, "override_reason": reason}

    if kernel_pseudo:
        return protect("kernel pseudo-process, not a workload")
    if is_protected(name or "?"):
        return protect("protected-process allowlist")
    if is_foreground:
        return protect("owns the foreground window (user-facing)")
    if fam["ood"]:
        return base | {"ai_class": "UNKNOWN", "safety_state": "PROTECT",
                       "recommendation": "PROTECT", "high_confidence": False,
                       "overridden": True,
                       "override_reason": "workload differs from training "
                                          f"distribution (familiarity {fam['familiarity']})"}
    if final < REVIEW_FLOOR:
        return base | {"ai_class": model_class, "safety_state": "PROTECT",
                       "recommendation": "PROTECT", "high_confidence": False,
                       "overridden": True,
                       "override_reason": f"insufficient confidence ({final} < {REVIEW_FLOOR})"}
    if final < THRESHOLD:
        return base | {"ai_class": model_class, "safety_state": "REVIEW",
                       "recommendation": "REVIEW / PROTECT",
                       "high_confidence": False, "overridden": True,
                       "override_reason": f"below action threshold ({final} < {THRESHOLD})"}
    state, rec = _STATE_REC[model_class]
    return base | {"ai_class": model_class if state != "PROTECT" else "PROTECTED",
                   "safety_state": state, "recommendation": rec,
                   "high_confidence": True, "overridden": state == "PROTECT",
                   "override_reason": "" if state != "PROTECT"
                   else "model voted PROTECTED with high familiar confidence"}
