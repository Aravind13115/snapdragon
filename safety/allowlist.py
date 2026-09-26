"""Protected-process allowlist. Phase-1 skeleton for the Phase-4 safety engine.

Nothing enforces termination in Phase 1 (no termination code exists),
but this registry already defines the shape: critical system processes
that must NEVER be acted upon in any later phase.
"""
from __future__ import annotations

ALWAYS_PROTECT = frozenset({
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
    "dwm.exe", "winlogon.exe",
})


def is_protected(name: str) -> bool:
    return (name or "").lower() in ALWAYS_PROTECT
