"""Safe recommendation mapping (Phase 2: recommendations ONLY).

    PROTECTED      -> PROTECT                      (never act)
    USER_IMPORTANT -> PROTECT                      (never disturb user work)
    FLEXIBLE       -> REDUCE BACKGROUND ACTIVITY   (suggestion text only)
    DEFERRABLE     -> DEFER WHEN APPROPRIATE       (suggestion text only)

Conservative rules:
  * confidence < threshold (0.85) -> "REVIEW / PROTECT" regardless of class.
  * allowlisted / protected-flagged processes -> PROTECTED/PROTECT even if
    the model says otherwise (the model has no authority over safety).
  * Nothing here touches any process; Phase 2 has no action executor.
"""
from __future__ import annotations

from safety.allowlist import is_protected

THRESHOLD = 0.85

CLASSES = ["PROTECTED", "USER_IMPORTANT", "FLEXIBLE", "DEFERRABLE"]

_RECOMMEND = {
    "PROTECTED": "PROTECT",
    "USER_IMPORTANT": "PROTECT",
    "FLEXIBLE": "REDUCE BACKGROUND ACTIVITY",
    "DEFERRABLE": "DEFER WHEN APPROPRIATE",
}


def decide(name: str, class_id: int, confidence: float,
           protected_flag: bool = False) -> dict:
    model_class = CLASSES[class_id] if 0 <= class_id < 4 else "DEFERRABLE"
    # Safety override: allowlist or protected feature wins over the model.
    if protected_flag or is_protected(name or "?"):
        return {"ai_class": "PROTECTED", "model_class": model_class,
                "confidence": 1.0 if protected_flag else round(confidence, 4),
                "recommendation": "PROTECT",
                "high_confidence": True,
                "overridden": True,
                "override_reason": "protected-process allowlist"}
    if confidence < THRESHOLD:
        return {"ai_class": model_class, "model_class": model_class,
                "confidence": round(confidence, 4),
                "recommendation": "REVIEW / PROTECT",
                "high_confidence": False,
                "overridden": False,
                "override_reason": f"confidence {confidence:.2f} < {THRESHOLD} threshold"}
    return {"ai_class": model_class, "model_class": model_class,
            "confidence": round(confidence, 4),
            "recommendation": _RECOMMEND[model_class],
            "high_confidence": True,
            "overridden": False, "override_reason": ""}
