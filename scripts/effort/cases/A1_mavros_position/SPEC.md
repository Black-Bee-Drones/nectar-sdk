---
id: A1_mavros_position
title: ArduPilot · MAVROS position nav
---

## Goal

Takeoff to 2 m, move 5 m forward in the body frame, land.

## Stack assumptions

ArduPilot + MAVROS; GPS pose; NavigationMethod.POSITION

## Success condition

Vehicle reaches setpoint within 0.3 m and lands.

## Non-goals

Not measuring tracking RMSE or timing.

## Counting

Application fixtures only. Nectar package internals are never counted.
Regions use `# @loc:boilerplate` / `# @loc:core` markers.
