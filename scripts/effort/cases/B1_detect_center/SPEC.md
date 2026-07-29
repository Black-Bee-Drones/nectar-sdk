---
id: B1_detect_center
title: Detect-and-center composition
---

## Goal

Takeoff, center on a detected class with body-velocity PID, land.

## Stack assumptions

ArduPilot MAVLink + VISION pose + webcam + YOLO Detector + PID

## Success condition

Target within CENTER_PX or lost-limit exit; orderly land.

## Non-goals

Not measuring detection mAP or tracking RMSE.

## Counting

Application fixtures only. Nectar package internals are never counted.
Regions use `# @loc:boilerplate` / `# @loc:core` markers.
