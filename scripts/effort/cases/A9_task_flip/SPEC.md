---
id: A9_task_flip
title: Learning task flip (detect / segment / classify)
parity_waiver: Without side sums two task scripts; cores are intentionally different task bodies.
effort_with: with_nectar.py
effort_without: without_segment.py,without_classify.py
---

## Goal

Unified task entry points vs separate framework scripts per task.

## Stack assumptions

Detector / Segmentor / Classifier vs task-specific APIs

## Success condition

Same call-site pattern across tasks on the With side.

## Non-goals

Not cross-task metric unification.

## Counting

Effort uses the multi-task With script vs both Without scripts.
Swap delta uses `with_detect.py` ↔ `with_segment.py` and
`without_segment.py` ↔ `without_classify.py`.
