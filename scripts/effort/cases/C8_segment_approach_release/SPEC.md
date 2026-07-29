---
id: C8_segment_approach_release
title: Multi-axis segment → confirm → approach → release
metric_role: swap_only
effort_with: with_stack_a.py
effort_without: without_stack_a.py
---

## Goal

Same multi-phase payload fragment under two stacks orthogonal to C7.
Measures accumulated interchange when firmware/transport, pose, camera,
Segmentor, Classifier, and range source change together while Core phases
stay fixed.

## Stack A

- ArduPilot · MAVROS
- `PoseSource.VISION`
- OAK-D (`ImageHandler("oakd")`)
- Ultralytics `Segmentor` + `Classifier`
- Range via OAK-D `get_distance`
- Payload via `do_servo` (HOLD→RELEASE PWM)

## Stack B

- PX4 · `px4_mavlink`
- `PoseSource.GPS`
- ROS RGB topic `/camera/color/image_raw` (e.g. RealSense color via ROS)
- Transformers `Segmentor` (MaskFormer) + `Classifier` (ViT)
- Range via `DistanceEstimator` (bbox height → meters)
- Payload via `set_actuator` HOLD→RELEASE

## Phases (Core — identical on all four scripts)

1. TAKEOFF
2. CENTER (PID on segment mask/bbox centroid)
3. CONFIRM (Classifier on ROI; fail → land)
4. APPROACH until `range_m ≤ STANDOFF_M`
5. HOLD → RELEASE payload adapters
6. LAND

## Success condition

Release after successful confirm+approach, or orderly land on lost/confirm fail.

## Non-goals

mAP/IoU; depth accuracy; RF-DETR; ColorDetector.

## Counting

`metric_role: swap_only`. Effort diagnostics use Stack A only. Interchange via
`compute_swap_delta.py` on Stack A ↔ Stack B pairs.
