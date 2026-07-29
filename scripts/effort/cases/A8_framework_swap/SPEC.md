---
id: A8_framework_swap
title: Learning framework swap
parity_waiver: Without side sums two framework scripts; core lines differ by API shape — waiver for multi-file without aggregate.
effort_with: with_nectar.py
effort_without: without_transformers.py,without_rfdetr.py
---

## Goal

Same detect call site across YOLO and Transformers/RF-DETR-style backends.

## Stack assumptions

Detector(framework=...) vs divergent Ultralytics and HF APIs

## Success condition

Caller uses one detect surface; only model/framework ids change.

## Non-goals

Not a accuracy bake-off between models.

## Counting

Effort uses the multi-framework With loop vs both Without scripts.
Swap delta uses `with_yolo.py` ↔ `with_transformers.py` and
`without_transformers.py` ↔ `without_rfdetr.py`.
