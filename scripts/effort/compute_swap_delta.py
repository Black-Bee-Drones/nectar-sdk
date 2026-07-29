#!/usr/bin/env python3
"""Compute paired With/Without swap deltas from swaps.yaml.

For each swap entry, diffs the two With paths and the two Without paths.
Counts physical non-blank, non-full-line-comment lines that differ
(excluding @loc marker lines). Emits results/swap_delta.json and .md.

Usage:
  python scripts/effort/compute_swap_delta.py
  python scripts/effort/compute_swap_delta.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

EFFORT_ROOT = Path(__file__).resolve().parent
CASES_ROOT = EFFORT_ROOT / "cases"
DEFAULT_SWAPS = EFFORT_ROOT / "swaps.yaml"
RESULTS = EFFORT_ROOT / "results"

LOC_MARKER_RE = re.compile(r"^#\s*@loc:(boilerplate|core):(begin|end)\s*$")
COMMENT_RE = re.compile(r"^\s*#")


def _load_swaps(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        return list(data.get("swaps") or [])
    return _parse_swaps_simple(text)


def _parse_swaps_simple(text: str) -> List[Dict[str, Any]]:
    """Parse the swaps.yaml shape without PyYAML."""
    swaps: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    list_key: Optional[str] = None
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if raw.startswith("swaps:"):
            continue
        if raw.startswith("  - name:"):
            if current:
                swaps.append(current)
            name = raw.split(":", 1)[1].strip().strip('"').strip("'")
            current = {
                "name": name,
                "with": [],
                "without": [],
                "axes": [],
                "kind": "single",
            }
            list_key = None
            continue
        if current is None:
            continue
        stripped = raw.strip()
        if stripped.startswith("case:"):
            current["case"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            list_key = None
        elif stripped.startswith("stays_fixed:"):
            current["stays_fixed"] = (
                stripped.split(":", 1)[1].strip().strip('"').strip("'")
            )
            list_key = None
        elif stripped.startswith("kind:"):
            current["kind"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            list_key = None
        elif stripped.startswith("axes:"):
            rest = stripped.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                current["axes"] = [
                    p.strip().strip('"').strip("'")
                    for p in inner.split(",")
                    if p.strip()
                ]
            else:
                list_key = "axes"
                current["axes"] = []
        elif stripped == "with:":
            list_key = "with"
        elif stripped == "without:":
            list_key = "without"
        elif stripped.startswith("without:") and stripped.endswith("[]"):
            current["without"] = []
            list_key = None
        elif stripped.startswith("with:") and stripped.endswith("[]"):
            current["with"] = []
            list_key = None
        elif stripped.startswith("- ") and list_key:
            current.setdefault(list_key, []).append(
                stripped[2:].strip().strip('"').strip("'")
            )
        else:
            list_key = None
    if current:
        swaps.append(current)
    return swaps


def _content_lines(path: Path) -> List[str]:
    lines: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if LOC_MARKER_RE.match(stripped):
            continue
        if COMMENT_RE.match(line) and not stripped.startswith("# @loc"):
            continue
        lines.append(line.rstrip())
    return lines


def _diff_line_count(path_a: Path, path_b: Path) -> Tuple[int, int]:
    import difflib

    if path_a.resolve() == path_b.resolve():
        return 0, 0
    a = _content_lines(path_a)
    b = _content_lines(path_b)
    if a == b:
        return 0, 0
    sm = difflib.SequenceMatcher(a=a, b=b)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        changed += max(i2 - i1, j2 - j1)
    return 1, changed


def _resolve(rel: str) -> Path:
    path = CASES_ROOT / rel
    if not path.is_file():
        raise FileNotFoundError(f"swap path not found: {rel} -> {path}")
    return path


def _pair_status(paths: Sequence[str]) -> Tuple[str, Optional[Tuple[Path, Path]]]:
    """Classify a swap pair.

    Returns (status, resolved_pair_or_None) where status is:
      ok            — two distinct existing files
      missing       — fewer than two paths declared
      same_file     — two paths resolve to the same file (invalid)
    """
    if len(paths) < 2:
        return "missing", None
    p0 = _resolve(paths[0])
    p1 = _resolve(paths[1])
    if p0.resolve() == p1.resolve():
        return "same_file", None
    return "ok", (p0, p1)


def _fmt_cell(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def compute(swaps_path: Path = DEFAULT_SWAPS) -> Dict[str, Any]:
    entries = _load_swaps(swaps_path)
    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    for item in entries:
        name = item.get("name", "")
        case = item.get("case", "")
        stays = item.get("stays_fixed", "")
        kind = item.get("kind") or "single"
        axes = item.get("axes") or []
        with_paths: Sequence[str] = item.get("with") or []
        without_paths: Sequence[str] = item.get("without") or []
        row: Dict[str, Any] = {
            "name": name,
            "case": case,
            "kind": kind,
            "axes": list(axes),
            "stays_fixed": stays,
            "with_files_changed": None,
            "with_lines_changed": None,
            "without_files_changed": None,
            "without_lines_changed": None,
            "with_pair": list(with_paths),
            "without_pair": list(without_paths),
            "with_pair_status": "missing",
            "without_pair_status": "missing",
        }
        try:
            w_status, w_pair = _pair_status(with_paths)
            row["with_pair_status"] = w_status
            if w_status == "ok" and w_pair is not None:
                wf, wl = _diff_line_count(w_pair[0], w_pair[1])
                row["with_files_changed"] = wf
                row["with_lines_changed"] = wl
            elif w_status == "same_file":
                errors.append(
                    f"{name}: with pair lists the same file twice "
                    f"({with_paths[0]!r}); declare two distinct variants or omit"
                )
            elif w_status == "missing" and len(with_paths) > 0:
                errors.append(
                    f"{name}: with pair needs two paths, got {len(with_paths)}"
                )

            o_status, o_pair = _pair_status(without_paths)
            row["without_pair_status"] = o_status
            if o_status == "ok" and o_pair is not None:
                of, ol = _diff_line_count(o_pair[0], o_pair[1])
                row["without_files_changed"] = of
                row["without_lines_changed"] = ol
            elif o_status == "same_file":
                errors.append(
                    f"{name}: without pair lists the same file twice "
                    f"({without_paths[0]!r}); use without: [] if no Without pair"
                )
            # missing without (empty list) is allowed — renders as "—"
        except FileNotFoundError as exc:
            errors.append(str(exc))
            row["error"] = str(exc)
        results.append(row)
    return {
        "description": (
            "Paired interchange cost. Lines = non-blank, non-full-line-comment "
            "source lines that differ between variant files (excluding @loc markers). "
            "Per difflib hunk: max(deleted, inserted). "
            "Incomplete pairs (missing or same-file) report null and render as —. "
            "Computed by compute_swap_delta.py from swaps.yaml. "
            "kind=single|multi; axes lists changed stack dimensions."
        ),
        "swaps_yaml": str(swaps_path),
        "swaps": results,
        "errors": errors,
    }


def _table_rows(items: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "| Swap | Case | Axes | With files | With lines | Without files | Without lines | What stays fixed |",
        "|------|------|------|-----------:|-----------:|--------------:|--------------:|------------------|",
    ]
    for item in items:
        axes = ", ".join(item.get("axes") or []) or "—"
        lines.append(
            f"| {item['name']} | `{item['case']}` | {axes} | "
            f"{_fmt_cell(item['with_files_changed'])} | "
            f"{_fmt_cell(item['with_lines_changed'])} | "
            f"{_fmt_cell(item['without_files_changed'])} | "
            f"{_fmt_cell(item['without_lines_changed'])} | {item['stays_fixed']} |"
        )
    return lines


def render_md(data: Dict[str, Any]) -> str:
    swaps = data.get("swaps") or []
    single = [s for s in swaps if (s.get("kind") or "single") != "multi"]
    multi = [s for s in swaps if (s.get("kind") or "single") == "multi"]
    lines = [
        "# Swap-delta results",
        "",
        "Paired With/Without interchange cost. Generated by "
        "`scripts/effort/compute_swap_delta.py` from `scripts/effort/swaps.yaml`.",
        "",
        "Incomplete Without pairs (none declared, or same file twice) show `—` "
        "rather than a spurious 0/0.",
        "",
        "## Single-axis swaps",
        "",
    ]
    lines.extend(_table_rows(single) if single else ["_(none)_", ""])
    lines.extend(["", "## Multi-axis swaps", ""])
    lines.extend(_table_rows(multi) if multi else ["_(none)_", ""])
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--swaps", type=Path, default=DEFAULT_SWAPS)
    parser.add_argument("--json-out", type=Path, default=RESULTS / "swap_delta.json")
    parser.add_argument("--md-out", type=Path, default=RESULTS / "swap_delta.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any swap path is missing or a pair is same-file",
    )
    args = parser.parse_args(argv)

    data = compute(args.swaps)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    args.md_out.write_text(render_md(data), encoding="utf-8")
    print(f"wrote {args.json_out}")
    print(f"wrote {args.md_out}")
    for err in data.get("errors", []):
        print(f"ERROR: {err}", file=sys.stderr)
    if args.check and data.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
