# Slide content — 8 slides (concise, presentation-ready)

## SLIDE 1 — Problem
Subtitle: Background work fights your foreground app — blindly.
Text: Windows shows CPU graphs but can't say which background work is safe
to defer. Users either defer nothing or kill the wrong process.
Visual: live dashboard process table (dashboard.png).
Takeaway: Utilization without understanding is unactionable.

## SLIDE 2 — Solution
Subtitle: Observe → Understand → Predict → Protect → Simulate.
Text: A local AI layer classifies every workload by context and only ever
proposes safe, simulated optimizations. Never kills, suspends, or disables.
Visual: pipeline diagram (03_architecture.md).
Takeaway: Intelligence with a safety-first guarantee.

## SLIDE 3 — AI Architecture
Subtitle: 1.9 KB neural net, fully local.
Text: 11 live signals → MLP 11→16→8→4 ONNX → temperature calibration →
familiarity (OOD) gating. Final = model × familiarity; uncertain → PROTECT.
Visual: model card + a WHY explanation row.
Takeaway: Tiny, explainable, conservative by construction.

## SLIDE 4 — Snapdragon / Hexagon NPU
Subtitle: Real NPU execution, measured.
Text: Same ONNX model compiled via Qualcomm AI Hub for Snapdragon X Elite
CRD: compile + link SUCCESS, profile shows all 10 nodes on NPU, inference
4/4 argmax agreement (max diff 0.0015). Target path: ONNX → QNN → Hexagon.
Visual: validation card screenshot + job IDs.
Takeaway: Not a mockup — real Hexagon NPU execution evidence.

## SLIDE 5 — Safety-first decision engine
Subtitle: The model advises; the safety layer decides.
Text: Allowlist, foreground, OOD, and confidence rules override any model
vote. Live: ~139 PROTECT / ~61 REVIEW, zero unwarranted candidates.
Emergency stop disables simulation while monitoring continues.
Visual: safety ring + a PROTECT row with reason.
Takeaway: Uncertainty protects the user — never authorizes action.

## SLIDE 6 — Live dashboard + demo
Subtitle: See it decide in 3 minutes.
Text: START DEMO (presenting): PowerPoint PROTECTED, sync/indexer
candidates → SIMULATE → projected HIGH→LOWER bars → decision log records
every step with reasons.
Visual: live dashboard (dashboard_full.png), decision history rows.
Takeaway: Full pipeline observable in one screen.

## SLIDE 7 — Validation and measurements
Subtitle: Measured only — nothing invented.
Text: CPU inference 0.024 ms/row · app ~1% CPU · ~70 MB · API <160 ms ·
NPU profile+inference VERIFIED · 74/74 tests. 87.38% is synthetic fit, not
real-world accuracy. No battery/CPU-savings claims.
Visual: measurements table (08_measurements.md).
Takeaway: Every number traceable to evidence.

## SLIDE 8 — Vision / conclusion
Subtitle: Built for Snapdragon HP PCs.
Text: Validated NPU model + proven safety architecture + local-first design
= ready for on-device deployment on Snapdragon X Elite HP machines, where
Hexagon NPU inference keeps AI monitoring off the CPU entirely.
Visual: architecture diagram + target device framing.
Takeaway: Stability → Safety → AI → NPU — in that order, ready to ship.
