---
id: A10_realsense
title: RealSense color frame
---

## Goal

Open a RealSense D4xx, read one color frame, close.

## Stack assumptions

`CameraFactory.from_source("realsense")` vs `pyrealsense2` color pipeline.

## Success condition

Frame shape printed; device closed.

## Non-goals

Depth metrics; alignment bake-off.

## Counting

Application fixtures only. Color stream only (fair counterpart to `get_frame()`).
