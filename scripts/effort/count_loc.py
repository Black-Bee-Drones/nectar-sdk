#!/usr/bin/env python3
"""Count Boilerplate / Core / Total SLOC for application-effort fixtures.

Rules:
  - Count non-blank, non-full-line-comment source lines (Python tokenize).
  - Docstrings (STRING tokens that are standalone statements) are not counted.
  - Every counted line must lie inside a tagged region:
        # @loc:boilerplate:begin ... # @loc:boilerplate:end
        # @loc:core:begin ... # @loc:core:end
  - Untagged counted lines cause a non-zero exit (use --check).
  - Nectar package internals are never counted (fixtures only).

Case aggregation:
  - with_* files  -> case["with"]
  - without_* files -> case["without"] (summed when multiple)

Usage:
  python scripts/effort/count_loc.py
  python scripts/effort/count_loc.py --check
  python scripts/effort/count_loc.py --json-out scripts/effort/results/loc_table.json
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

BEGIN_RE = re.compile(r"^#\s*@loc:(boilerplate|core):begin\s*$")
END_RE = re.compile(r"^#\s*@loc:(boilerplate|core):end\s*$")
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

EFFORT_ROOT = Path(__file__).resolve().parent
CASES_ROOT = EFFORT_ROOT / "cases"


def _parse_spec_front_matter(case_dir: Path) -> Dict[str, str]:
    """Parse simple key: value pairs from SPEC.md YAML front-matter."""
    spec = case_dir / "SPEC.md"
    if not spec.is_file():
        return {}
    text = spec.read_text(encoding="utf-8")
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}
    meta: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    return meta


def _logical_code_lines(source: str) -> Set[int]:
    """1-indexed line numbers that contain countable source code."""
    code_lines: Set[int] = set()
    # Track whether the next STRING at a given indent is a docstring.
    # Simpler rule: any STRING token whose line (after strip) starts with
    # a triple-quote and that is the only expression on the line is a docstring
    # candidate; we skip all lines covered by docstring STRING tokens that
    # appear as the first statement after ENCODING/NL or after INDENT following
    # def/class, and also module docstrings.
    prev_significant: Optional[int] = None
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(source.encode("utf-8")).readline))
    except tokenize.TokenError as exc:
        raise ValueError(f"tokenize failed: {exc}") from exc

    skip_string_lines: Set[int] = set()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type in (
            tokenize.ENCODING,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
            tokenize.COMMENT,
        ):
            i += 1
            continue

        if tok.type == tokenize.STRING:
            # Docstring if previous significant token was ENCODING-start,
            # NEWLINE after def/class suite start (INDENT), or start of file.
            is_doc = False
            if prev_significant is None:
                is_doc = True
            else:
                # Look back for INDENT or NEWLINE after COLON of def/class
                j = i - 1
                while j >= 0 and tokens[j].type in (
                    tokenize.NL,
                    tokenize.NEWLINE,
                    tokenize.INDENT,
                    tokenize.COMMENT,
                    tokenize.ENCODING,
                    tokenize.DEDENT,
                ):
                    if tokens[j].type == tokenize.INDENT:
                        is_doc = True
                        break
                    j -= 1
                if not is_doc and j >= 0 and tokens[j].type == tokenize.NEWLINE:
                    # module-level consecutive string after newline at column 0
                    if tok.start[1] == 0:
                        is_doc = True
            if is_doc:
                for ln in range(tok.start[0], tok.end[0] + 1):
                    skip_string_lines.add(ln)
                prev_significant = tok.type
                i += 1
                continue

        # Non-docstring significant token
        for ln in range(tok.start[0], tok.end[0] + 1):
            if ln not in skip_string_lines:
                code_lines.add(ln)
        prev_significant = tok.type
        i += 1

    # Drop lines that are only whitespace
    physical = source.splitlines()
    return {
        ln for ln in code_lines if 1 <= ln <= len(physical) and physical[ln - 1].strip()
    }


def _regions(source: str) -> List[Tuple[str, int, int]]:
    """Return list of (bucket, start_line, end_line) inclusive, 1-indexed, for content lines."""
    regions: List[Tuple[str, int, int]] = []
    stack: List[Tuple[str, int]] = []
    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        m_begin = BEGIN_RE.match(stripped)
        if m_begin:
            stack.append((m_begin.group(1), i + 1))  # content starts next line
            continue
        m_end = END_RE.match(stripped)
        if m_end:
            bucket = m_end.group(1)
            if not stack or stack[-1][0] != bucket:
                raise ValueError(f"line {i}: unmatched @loc:{bucket}:end")
            start_bucket, start_line = stack.pop()
            end_line = i - 1
            if end_line >= start_line:
                regions.append((start_bucket, start_line, end_line))
            continue
    if stack:
        raise ValueError(f"unclosed region(s): {[s[0] for s in stack]}")
    return regions


def _bucket_for_line(
    regions: List[Tuple[str, int, int]], line_no: int
) -> Optional[str]:
    for bucket, start, end in regions:
        if start <= line_no <= end:
            return bucket
    return None


def count_file(path: Path) -> Dict[str, int]:
    source = path.read_text(encoding="utf-8")
    code_lines = _logical_code_lines(source)
    regions = _regions(source)
    counts = {"boilerplate": 0, "core": 0, "total": 0, "untagged": 0}
    untagged: List[int] = []
    for ln in sorted(code_lines):
        # Marker lines themselves are comments — already excluded.
        bucket = _bucket_for_line(regions, ln)
        if bucket is None:
            counts["untagged"] += 1
            untagged.append(ln)
            continue
        counts[bucket] += 1
        counts["total"] += 1
    return {**counts, "untagged_lines": untagged}  # type: ignore[dict-item]


def _is_with_file(name: str) -> bool:
    return name.startswith("with_") and name.endswith(".py")


def _is_without_file(name: str) -> bool:
    return name.startswith("without_") and name.endswith(".py")


def iter_case_dirs(cases_root: Path = CASES_ROOT) -> Iterable[Path]:
    if not cases_root.is_dir():
        return []
    return sorted(
        p for p in cases_root.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def count_case(case_dir: Path) -> Dict:
    meta = _parse_spec_front_matter(case_dir)
    all_with = sorted(
        p for p in case_dir.iterdir() if p.is_file() and _is_with_file(p.name)
    )
    all_without = sorted(
        p for p in case_dir.iterdir() if p.is_file() and _is_without_file(p.name)
    )
    if not all_with and not all_without:
        return {
            "id": case_dir.name,
            "with": None,
            "without": None,
            "files": {},
            "metric_role": meta.get("metric_role", "effort"),
            "errors": [f"no with_/without_ python fixtures in {case_dir.name}"],
        }

    # Count every fixture file for diagnostics; effort aggregates may use a subset.
    files: Dict[str, Dict] = {}
    errors: List[str] = []

    def count_paths(paths: List[Path]) -> None:
        for path in paths:
            try:
                result = count_file(path)
            except ValueError as exc:
                errors.append(f"{path.name}: {exc}")
                continue
            files[path.name] = {
                "boilerplate": result["boilerplate"],
                "core": result["core"],
                "total": result["total"],
                "untagged": result["untagged"],
                "untagged_lines": result["untagged_lines"],
            }
            if result["untagged"]:
                errors.append(
                    f"{case_dir.name}/{path.name}: {result['untagged']} untagged code "
                    f"line(s): {result['untagged_lines']}"
                )

    count_paths(all_with)
    count_paths(all_without)

    def resolve_side(kind: str, all_paths: List[Path]) -> List[Path]:
        key = f"effort_{kind}"
        if key in meta:
            names = [n.strip() for n in meta[key].split(",") if n.strip()]
            resolved: List[Path] = []
            for name in names:
                path = case_dir / name
                if not path.is_file():
                    errors.append(
                        f"{case_dir.name}: effort_{kind} file missing: {name}"
                    )
                    continue
                resolved.append(path)
            return resolved
        return all_paths

    def sum_side(paths: List[Path]) -> Optional[Dict[str, int]]:
        if not paths:
            return None
        agg = {"boilerplate": 0, "core": 0, "total": 0}
        for path in paths:
            entry = files.get(path.name)
            if entry is None:
                continue
            for key in ("boilerplate", "core", "total"):
                agg[key] += entry[key]  # type: ignore[operator]
        return agg

    effort_with = resolve_side("with", all_with)
    effort_without = resolve_side("without", all_without)

    return {
        "id": case_dir.name,
        "with": sum_side(effort_with),
        "without": sum_side(effort_without),
        "effort_with_files": [p.name for p in effort_with],
        "effort_without_files": [p.name for p in effort_without],
        "files": files,
        "metric_role": meta.get("metric_role", "effort"),
        "errors": errors,
    }


def count_all(cases_root: Path = CASES_ROOT) -> Dict:
    cases = [count_case(d) for d in iter_case_dirs(cases_root)]
    errors = [e for c in cases for e in c.get("errors", [])]
    return {
        "cases_root": str(cases_root),
        "counting": {
            "method": "python-tokenize-sloc",
            "includes": "non-blank non-full-line-comment non-docstring lines inside @loc regions",
            "excludes": "nectar package internals; blanks; comments; docstrings; untagged fails check",
            "regions": ["boilerplate", "core"],
        },
        "cases": cases,
        "errors": errors,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases-root",
        type=Path,
        default=CASES_ROOT,
        help="Directory containing case subdirectories",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any case has errors (untagged lines, bad regions)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors / summary",
    )
    args = parser.parse_args(argv)

    report = count_all(args.cases_root)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        # Strip untagged_lines detail from stable output? Keep for debug; render uses aggregates.
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        for case in report["cases"]:
            w = case.get("with") or {"boilerplate": "-", "core": "-", "total": "-"}
            wo = case.get("without") or {"boilerplate": "-", "core": "-", "total": "-"}
            print(
                f"{case['id']}: "
                f"with B/C/T={w['boilerplate']}/{w['core']}/{w['total']}  "
                f"without B/C/T={wo['boilerplate']}/{wo['core']}/{wo['total']}"
            )
            for err in case.get("errors", []):
                print(f"  ERROR: {err}", file=sys.stderr)

    if args.check and report["errors"]:
        print(f"{len(report['errors'])} error(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
