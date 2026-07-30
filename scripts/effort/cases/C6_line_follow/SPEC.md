---
id: C6_line_follow
title: Color line acquire → follow → end
effort_with: with_nectar.py
effort_without: without_nectar.py
---

## Goal

Takeoff, ACQUIRE a colored line (`RotatedRect`), FOLLOW with body-velocity PID on
lateral image error (and forward cruise), END after `LOST_LIMIT` frames without a
line or `FOLLOW_TIMEOUT_S`, then land. Representative of classical line-follow
control.

## Stack assumptions

- ArduPilot over MAVROS
- `PoseSource.VISION`
- USB webcam (effort primary); OAK-D camera swap variant
- Nectar `LineDetector` + `RotatedRect` (Without: OpenCV color mask + minAreaRect)

## Phases (Core)

1. TAKEOFF
2. ACQUIRE (wait until line center is finite)
3. FOLLOW (PID on `center_x` error; constant `CRUISE_VX`)
4. END (lost or timeout)
5. LAND

## Success condition

Follow runs until end condition; orderly land.

## Non-goals

Line-method bake-off metrics; color calibration suites.

## Counting

Application fixtures only. Identical gains/thresholds on both sides.

Variants `with_oakd.py` / `without_oakd.py` are for paired camera swap deltas.
