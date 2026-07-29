# Application effort comparison

Paired **With Nectar** and **Without Nectar** scripts for the same tasks.
Counts are application-side source lines only.

Short narrative counterparts: [`../../with-without.md`](../../with-without.md).
Longer tagged mission fragments live in `cases/C*`.

## Metrics

| Symbol | Meaning |
|--------|---------|
| B | Boilerplate — session, transport, and driver glue |
| C | Core — mission behavior (phases, waypoints, loops, filters) |
| T | Total = B + C |

Lines are tagged in fixtures:

```python
# @loc:boilerplate:begin
...
# @loc:boilerplate:end
# @loc:core:begin
...
# @loc:core:end
```

## Counting rules

- Python `tokenize` SLOC: non-blank, non-full-line-comment, non-docstring
- Every counted line must sit in a `@loc:boilerplate` or `@loc:core` region
- Untagged code lines fail `--check`
- Package code under `nectar/nectar/**` is never counted
- Core parity: `|C_with − C_without| / max(C) ≤ 25%` unless `parity_waiver:` is set in the case `SPEC.md`
- Cases with transport/camera variants declare `effort_with` / `effort_without` in `SPEC.md` so swap variants are not summed into effort totals
- `metric_role: swap_only` cases appear in interchange results, not in the default T-reduction summary

## Interchange (paired swap delta)

Stack switches are declared in [`swaps.yaml`](swaps.yaml). Each entry has:

- `kind: single` or `kind: multi` — one axis vs several axes at once
- `axes:` — e.g. `[transport]`, `[camera]`, `[transport, pose, camera, detector]`

`compute_swap_delta.py` diffs the With variant pair and the Without variant pair
and reports files/lines changed on each side. A pair needs two **distinct**
files; use `without: []` when there is no Without sibling (renders as `—`, not
`0`). Results split into single-axis and multi-axis tables.

## Reproduce

```bash
# From nectar-sdk root
python3 scripts/effort/count_loc.py --check --json-out scripts/effort/results/loc_table.json
python3 scripts/effort/check_core_parity.py --check
python3 scripts/effort/compute_swap_delta.py
python3 scripts/effort/render_results.py --from-count
```

Results: [`results/loc_table.md`](results/loc_table.md), [`results/swap_delta.md`](results/swap_delta.md).

## Case index

| ID | Title | Role |
|----|-------|------|
| A1–A3 | Position nav over MAVROS / MAVLink / PX4 DDS | effort + transport swap |
| A4 | Pose source GPS vs VISION | swap only |
| A5–A6 | Webcam / ROS image acquisition | effort + camera swap |
| A7–A9 | YOLO detect / framework swap / task flip | effort + learning swap |
| A10 | RealSense color frame | effort + camera swap |
| A11 | OAK-D color frame | effort + camera swap |
| B1–B2 | Detect-and-center / ArUco-center compositions | effort |
| C1_gate_sequence | Sequential gate search → align → pass | effort + transport / detector swap |
| C2_marker_station | Marker search → center → approach → settle | effort |
| C3_outdoor_survey | GPS waypoints + hover detect/log | effort + camera swap |
| C4_pose_portable | Pose-portable patrol (GPS↔VISION; matched Without) | swap only |
| C5_hook_release | Center → approach → servo release | effort |
| C6_line_follow | Color line acquire → follow → end | effort + camera swap |
| C7_stack_portable | Detect-and-center under two full stacks | swap only (multi-axis) |
| C8_segment_approach_release | Segment→confirm→approach→release (orthogonal stacks) | swap only (multi-axis) |
