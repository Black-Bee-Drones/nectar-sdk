---
id: C5_hook_release
title: Center → approach → servo release
---

## Goal

Takeoff, CENTER on a detected target class with body-velocity PID, APPROACH until
a range proxy band, command HOLD then RELEASE PWM on a servo channel, then land.
Representative of payload-release fragments that combine perception and actuators.

## Stack assumptions

- ArduPilot over MAVROS
- `PoseSource.GPS`
- USB webcam
- YOLO `Detector`
- `do_servo` / `MAV_CMD_DO_SET_SERVO`

## Phases (Core)

1. TAKEOFF
2. CENTER (image error within `CENTER_PX`)
3. APPROACH (bbox height / image height ≥ `APPROACH_RATIO`)
4. HOLD PWM → delay → RELEASE PWM
5. LAND

## Success condition

Release sequence commanded after approach band; orderly land.

## Non-goals

Segmentation bake-off; full multi-state hook mission trees.

## Counting

Application fixtures only. Identical constants on With and Without sides.
