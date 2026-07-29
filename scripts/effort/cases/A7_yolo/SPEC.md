---
id: A7_yolo
title: YOLO detection entry
---

## Goal

Run a single-frame detection and obtain a stable result shape.

## Stack assumptions

Ultralytics vs nectar.ai.detection.Detector

## Success condition

Boxes/classes available to the caller.

## Non-goals

Not measuring mAP or inference latency.

## Counting

Application fixtures only. Nectar package internals are never counted.
Regions use `# @loc:boilerplate` / `# @loc:core` markers.
