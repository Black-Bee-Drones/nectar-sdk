---
id: C2_marker_station
title: Marker station search → center → approach → settle
---

## Goal

Takeoff, wait until an ArUco marker is visible (SEARCH), CENTER with body-velocity
PID, APPROACH to a standoff along marker Z, SETTLE with confirmations, then land.
Representative of classical indoor station approach.

## Stack assumptions

- ArduPilot over MAVROS
- `PoseSource.VISION`
- ROS image topic via `ImageHandler`
- Nectar `Aruco` pose estimate

## Phases (Core)

1. TAKEOFF
2. SEARCH (wait for marker or lost-limit abort)
3. CENTER (xy within `CENTER_XY`)
4. APPROACH (range to `STANDOFF_M ± TOL_M`)
5. SETTLE (`SETTLE_CONFIRM` frames in band)
6. LAND

## Success condition

Marker settled in standoff band, then land.

## Non-goals

Calibration accuracy bake-off; marker dictionary bake-off.

## Counting

Application fixtures only. Identical mission constants on With and Without sides.
