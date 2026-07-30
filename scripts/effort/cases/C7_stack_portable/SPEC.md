---
id: C7_stack_portable
title: Multi-axis stack port (detect-and-center)
metric_role: swap_only
effort_with: with_stack_a.py
effort_without: without_stack_a.py
---

## Goal

Same detect-and-center mission under two divergent full stacks. Measures
accumulated interchange cost when firmware/transport, pose, camera, and detector
change together while Core phases stay fixed.

## Stack A

- ArduPilot · MAVLink
- `PoseSource.VISION`
- webcam
- YOLO `yolov8n.pt`

## Stack B

- PX4 · uXRCE-DDS
- `PoseSource.GPS`
- RealSense color
- Transformers DETR (`facebook/detr-resnet-50`)

## Phases (Core — identical on all four scripts)

1. TAKEOFF
2. DETECT-AND-CENTER (PID body velocity until `CENTER_PX` or `LOST_LIMIT`)
3. LAND

## Success condition

Target centered or lost-limit exit; orderly land.

## Non-goals

Detection mAP; tracking RMSE; depth quality.

## Counting

`metric_role: swap_only`. Effort diagnostics use Stack A only. Interchange measured
by `compute_swap_delta.py` on Stack A ↔ Stack B pairs.
