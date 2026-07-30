---
id: A11_oakd
title: OAK-D color frame
---

## Goal

Open an OAK-D, read one color frame, close.

## Stack assumptions

`CameraFactory.from_source("oakd")` vs `depthai` color pipeline.

## Success condition

Frame shape printed; device closed.

## Non-goals

Depth or neural-inference bake-off.

## Counting

Application fixtures only. Color stream only.
