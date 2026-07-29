---
id: C4_pose_portable
title: Pose-source portable patrol
metric_role: swap_only
effort_with: with_gps.py
effort_without: without_gps_patrol.py
---

## Goal

Run the same short patrol mission body under GPS pose and under VISION pose,
changing only the pose configuration on the With side, and measuring the matched
Without rewrite (GPS patrol ↔ VISION patrol with relay started).

## Stack assumptions

- ArduPilot MAVROS
- Shared mission: takeoff → two local moves → land
- GPS variant: `PoseSource.GPS` / Without without relay
- VISION variant: `PoseSource.VISION` / Without embeds VSLAM→`vision_pose` relay
- `without_vision_relay.py` is an isolated relay vignette only (not the swap pair)

## Success condition

Mission Core identical across `with_gps` / `with_vision` and across
`without_gps_patrol` / `without_vision_patrol`; only pose wiring differs.

## Non-goals

Not measuring VSLAM accuracy.

## Counting

- `metric_role: swap_only` — excluded from default T-reduction summary
- Effort diagnostics use `with_gps.py` vs `without_gps_patrol.py` only
- Interchange: `compute_swap_delta.py` on With GPS↔VISION and Without
  `without_gps_patrol.py` ↔ `without_vision_patrol.py`
