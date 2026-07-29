---
id: A4_pose_source
title: Pose source GPS vs VISION
metric_role: swap_only
parity_waiver: Without fixture is the vision-pose bridge only; effort comparison is not the primary metric.
effort_with: with_gps.py
effort_without: without_nectar.py
---

## Goal

Show mission body unchanged when PoseSource flips GPS to VISION.

## Stack assumptions

MAVROS; PoseSource enum (with) vs vision-pose bridge wiring (without)

## Success condition

Only pose delivery config/wiring differs. `with_gps.py` and `with_vision.py`
share the same takeoff/land core.

## Non-goals

Not a full flight; illustrates interchange delta.

## Counting

`metric_role: swap_only`. Interchange measured by `compute_swap_delta.py` on
`with_gps.py` ↔ `with_vision.py` only. There is no GPS↔VISION Without pair
(`without: []` in `swaps.yaml`); the Without column renders as `—`. The
vision-pose relay (`without_nectar.py`) documents extra Without wiring and is
counted in the effort diagnostics row. Matched GPS↔VISION Without patrol
interchange (same Core + relay started) is covered by `C4_pose_portable`.
