#!/usr/bin/env python3
"""Check Core SLOC parity between with_ and without_ sides of each case.

Enforces:
  |C_with - C_without| / max(C_with, C_without) <= threshold
Default threshold: 0.25.

Parity waiver: SPEC.md YAML front-matter may include:
  ---
  parity_waiver: reason text
  ---
When present, that case is reported but does not fail --check.

Usage:
  python scripts/effort/check_core_parity.py
  python scripts/effort/check_core_parity.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from count_loc import CASES_ROOT, count_all  # noqa: E402

DEFAULT_THRESHOLD = 0.25
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _parity_waiver(case_dir: Path) -> Optional[str]:
    spec = case_dir / "SPEC.md"
    if not spec.is_file():
        return None
    text = spec.read_text(encoding="utf-8")
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.strip().startswith("parity_waiver:"):
            return line.split(":", 1)[1].strip() or "(waiver present)"
    return None


def _ratio(c_with: int, c_without: int) -> float:
    denom = max(c_with, c_without)
    if denom == 0:
        return 0.0
    return abs(c_with - c_without) / denom


def check_cases(
    cases_root: Path = CASES_ROOT,
    threshold: float = DEFAULT_THRESHOLD,
) -> Tuple[List[Dict], List[str]]:
    report = count_all(cases_root)
    rows: List[Dict] = []
    failures: List[str] = []
    for case in report["cases"]:
        case_dir = cases_root / case["id"]
        waiver = _parity_waiver(case_dir)
        w = case.get("with")
        wo = case.get("without")
        row = {
            "id": case["id"],
            "core_with": None if w is None else w["core"],
            "core_without": None if wo is None else wo["core"],
            "ratio": None,
            "waiver": waiver,
            "ok": True,
            "detail": "",
        }
        if w is None or wo is None:
            row["ok"] = False
            row["detail"] = "missing with or without side"
            if not waiver:
                failures.append(f"{case['id']}: missing with or without side")
            rows.append(row)
            continue
        ratio = _ratio(w["core"], wo["core"])
        row["ratio"] = round(ratio, 4)
        if ratio > threshold:
            row["ok"] = False
            row["detail"] = (
                f"core parity {ratio:.2%} exceeds {threshold:.0%} "
                f"(with={w['core']}, without={wo['core']})"
            )
            if waiver:
                row["detail"] += f" [waived: {waiver}]"
                row["ok"] = True
            else:
                failures.append(f"{case['id']}: {row['detail']}")
        rows.append(row)
    # Also surface count_loc structural errors
    for err in report.get("errors", []):
        failures.append(err)
    return rows, failures


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-root", type=Path, default=CASES_ROOT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rows, failures = check_cases(args.cases_root, args.threshold)
    for row in rows:
        status = "OK" if row["ok"] else "FAIL"
        print(
            f"{row['id']}: {status}  "
            f"C_with={row['core_with']} C_without={row['core_without']} "
            f"ratio={row['ratio']} {row['detail']}"
        )
    if args.check and failures:
        print(f"{len(failures)} parity/count failure(s)", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
