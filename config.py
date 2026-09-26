# Snapdragon Optimizer — Phase 5 (competition prototype)
#
# WHAT THIS IS
#   Read-only system telemetry + dashboard. No process termination,
#   suspension, priority change, or any other system modification.
#
# PHASE MAP
#   Phase 1 (this): platform detection, real CPU/RAM/disk/net/battery
#                   telemetry, read-only process list, dashboard,
#                   stub interfaces for later phases.
#   Phase 2: ONNX classifier plugs into inference/base.py
#   Phase 3: Qualcomm QNN / Hexagon NPU backend plugs into inference/qnn_backend.py
#   Phase 4: safety engine enforcement + reversible optimization in
#            safety/engine.py and optimization/planner.py
#
# SAFETY INVARIANT (all phases): Phase 1 code paths must never call
#   terminate/kill/suspend/nice/priority APIs. See safety/engine.py.

APP_NAME = "snapdragon-observe"
VERSION = "0.3.0-phase3"
PORT = 8099
REFRESH_MS = 2000

# Later phases read this to decide which model/backend to load.
# Phase 1 only reports it.
SUPPORTED_ARCHES = ("x86_64", "AMD64", "ARM64", "aarch64")
