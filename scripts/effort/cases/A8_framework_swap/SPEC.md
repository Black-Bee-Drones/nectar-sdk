---
id: A8_framework_swap
title: Learning framework swap
effort_with: with_yolo.py
effort_without: without_yolo.py
---

## Goal

Same detect call site across YOLO, Transformers DETR, and RF-DETR backends.

## Stack assumptions

`Detector(framework=...)` vs Ultralytics / HuggingFace / RF-DETR raw APIs.

## Success condition

Caller uses one detect surface; only model/framework ids change.

## Non-goals

Not an accuracy bake-off between models.

## Counting

Effort: `with_yolo.py` ↔ `without_yolo.py`.
Swap deltas: YOLO↔Transformers and YOLO↔RF-DETR with matched Without pairs.
`with_nectar.py` is a multi-framework vignette (not in the effort row).
