---
id: B2_aruco_center
title: ArUco-center composition
---

## Goal

Takeoff, center on ArUco marker with body-velocity PID, land.

## Stack assumptions

PX4 uXRCE-DDS + GPS local pose + ROS image + ArUco + PID

## Success condition

Marker within CENTER_PX or lost-limit exit; orderly land.

## Non-goals

Not measuring pose accuracy.

## Counting

Application fixtures only. Nectar package internals are never counted.
Regions use `# @loc:boilerplate` / `# @loc:core` markers.
