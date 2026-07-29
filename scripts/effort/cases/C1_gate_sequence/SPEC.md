---
id: C1_gate_sequence
title: Sequential gate search → align → pass
effort_with: with_mavlink.py
effort_without: without_mavlink.py
---

## Goal

Takeoff, then for each of `N_GATES` gates: SEARCH with a lateral/vertical sweep,
ALIGN with body-velocity PID until `CENTER_CONFIRM` frames, PASS forward by
`PASS_M`, then land. Representative of indoor sequential-gate visual control.

## Stack assumptions

- ArduPilot over direct MAVLink (effort primary); MAVROS / PX4 DDS transport variants
- `PoseSource.VISION`
- USB webcam
- YOLO `Detector` (Transformers DETR variant for detector swap)

## Phases (Core — identical on With and Without)

1. TAKEOFF
2. For gate in `1..N_GATES`:
   - SEARCH (sweep until detection or abort)
   - ALIGN (PID center + confirmations; lost-detection abort)
   - PASS (body-forward `PASS_M`)
3. LAND

## Success condition

All gates passed (or orderly abort on search/align failure), then land.

## Non-goals

Detection mAP, tracking RMSE, or competition scoring.

## Counting

Application fixtures only. Transport/detector variants are for paired swap deltas;
effort totals use `effort_with` / `effort_without` above.
