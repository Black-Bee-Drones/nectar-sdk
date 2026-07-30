---
id: A9_task_flip
title: Learning task flip (detect / segment / classify)
effort_with: with_detect.py
effort_without: without_detect.py
---

## Goal

Unified task entry points vs separate framework scripts per task.

## Stack assumptions

`Detector` / `Segmentor` / `Classifier` vs task-specific Ultralytics APIs.

## Success condition

Same load → call → iterate/print pattern across tasks on the With side.

## Non-goals

Not cross-task metric unification.

## Counting

Effort: `with_detect.py` ↔ `without_detect.py`.
Swap deltas: detect↔segment and segment↔classify with matched Without pairs.
`with_nectar.py` is a multi-task vignette (not in the effort row).
