---
id: A12_bebop_hover
title: Bebop velocity hover atom
---

## Goal

Minimal Bebop flight: takeoff → short body-frame velocity move → land.

## Stack assumptions

`DroneFactory.create("bebop", BebopConfig(...))` vs `ros2_bebop_driver` topics
(`/{ns}/takeoff`, `/{ns}/cmd_vel`, `/{ns}/land`).

## Success condition

Same Core sequence on both sides; Without is topic publishers only.

## Non-goals

Not a capability bake-off vs PX4/ArduPilot. Bebop has no position `move_to`
in this stack — velocity only. Altitude argument on takeoff is advisory
(driver default hover height).

## Counting

Capability-limited Tier A atom. No Bebop↔Crazyflie swap (Core APIs differ).
