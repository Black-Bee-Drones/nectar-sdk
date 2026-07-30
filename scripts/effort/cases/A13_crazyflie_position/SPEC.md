---
id: A13_crazyflie_position
title: Crazyflie position atom
---

## Goal

Minimal Crazyflie flight: takeoff → short `move_to` / `go_to` → land.

## Stack assumptions

`DroneFactory.create("crazyflie", CrazyflieConfig(...))` vs Crazyswarm2
services (`/<cf>/takeoff`, `/<cf>/go_to`, `/<cf>/land`).

## Success condition

Same Core sequence on both sides; Without is service clients only.

## Non-goals

Not a capability bake-off vs PX4/ArduPilot. Crazyflie position uses onboard
`goTo` (no GPS). Takeoff height and goTo duration follow Crazyswarm2 quirks
documented in the Crazyflie module README.

## Counting

Capability-limited Tier A atom. No Bebop↔Crazyflie swap (Core APIs differ).
