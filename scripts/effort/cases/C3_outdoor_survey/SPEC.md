---
id: C3_outdoor_survey
title: Outdoor GPS survey + hover detect/log
effort_with: with_webcam.py
effort_without: without_webcam.py
---

## Goal

Takeoff under GPS pose, visit each waypoint with POSITION navigation, hover for
`HOVER_S` seconds while running a detector and logging class/confidence, then
land. Representative of outdoor field survey + perception.

## Stack assumptions

- ArduPilot over MAVROS
- `PoseSource.GPS`
- `NavigationMethod.POSITION`
- Webcam (effort primary); ROS / RealSense camera swap variants
- YOLO `Detector`

## Phases (Core)

1. TAKEOFF
2. For each waypoint: MOVE → HOVER window → DETECT+log detections
3. LAND

## Success condition

All waypoints visited; at least one detection attempt per hover; orderly land.

## Non-goals

Coverage completeness metrics; detection mAP.

## Counting

Variants `with_ros_cam.py` / `without_ros_cam.py` are for paired camera swap
deltas; effort totals use `effort_with` / `effort_without` above.
