"""Functional verification harness for the Nectar SDK (tier 2).

Every check performs a *real operation*: it detects a synthetic ArUco marker,
runs a PID step response to convergence, completes a MAVLink heartbeat handshake
over a UDP loopback, opens the Qt window offscreen, runs a nano-model inference,
and so on.

Checks self-skip (never fail) when a camera, GPU, simulator, or optional
dependency is missing, so the same harness runs unchanged in Docker CI and on
real hardware -- and the result tells you what actually works on this setup.

Each module runs in its own subprocess: rclpy contexts, Qt, and torch do not
compose cleanly in a single process, and isolation means one crashing check
cannot take down the run. Results are collected and printed grouped, mirroring
the look of ``setup.sh verify``.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import os
import subprocess
import sys
import tempfile
from typing import Callable, List, Optional

# Status values.
PASS = "pass"
SKIP = "skip"
FAIL = "fail"

# Canonical module order. Only files that actually exist are run, so the
# harness grows cleanly as modules are added.
_ALL_MODULES = [
    "core",
    "vision",
    "control",
    "sensors",
    "localization",
    "interface",
    "ai",
    "simulation",
    "crazyflie",
]

# Per-module subprocess timeout (seconds). AI may download model weights on the
# first run; simulation may step a headless Gazebo world.
_TIMEOUTS = {
    "ai": 600,
    "simulation": 180,
    "interface": 120,
    "crazyflie": 120,
}
_DEFAULT_TIMEOUT = 120

# Colors (match scripts/lib/common.sh). Disabled when not a TTY or NO_COLOR set.
_RED = "\033[0;31m"
_GREEN = "\033[0;32m"
_YELLOW = "\033[1;33m"
_BLUE = "\033[0;34m"
_PURPLE = "\033[0;35m"
_NC = "\033[0m"


def _color_enabled() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(color: str, text: str) -> str:
    return f"{color}{text}{_NC}" if _color_enabled() else text


class Skip(Exception):
    """Raise from a check to mark it skipped (dependency/device/sim absent)."""


class Fail(Exception):
    """Raise from a check to mark it failed with a message."""


@dataclasses.dataclass
class Result:
    name: str
    status: str
    detail: str = ""


@dataclasses.dataclass
class Check:
    name: str
    fn: Callable[[], Optional[str]]


@dataclasses.dataclass
class ModuleSpec:
    key: str
    title: str
    install: str
    checks: List[Check]


def _modules_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def available_modules() -> List[str]:
    here = _modules_dir()
    return [k for k in _ALL_MODULES if os.path.exists(os.path.join(here, f"{k}.py"))]


def load_spec(key: str) -> ModuleSpec:
    mod = importlib.import_module(f"nectar.diagnostics.{key}")
    return mod.MODULE


def run_check(check: Check) -> Result:
    try:
        detail = check.fn() or ""
        return Result(check.name, PASS, str(detail))
    except Skip as exc:
        return Result(check.name, SKIP, str(exc))
    except Fail as exc:
        return Result(check.name, FAIL, str(exc))
    except Exception as exc:  # noqa: BLE001 - any unexpected error is a failure
        return Result(check.name, FAIL, f"{type(exc).__name__}: {exc}")


def run_module_inproc(key: str) -> List[Result]:
    spec = load_spec(key)
    return [run_check(c) for c in spec.checks]


# --- worker mode -----------------------------------------------------------


def _worker(key: str, out_path: Optional[str]) -> int:
    """Run one module's checks in this process and emit JSON results."""
    try:
        spec = load_spec(key)
        title, install = spec.title, spec.install
        results = [run_check(c) for c in spec.checks]
    except Exception as exc:  # noqa: BLE001 - import/spec failure for the whole module
        title, install = key, ""
        results = [Result(f"{key}: load module", FAIL, f"{type(exc).__name__}: {exc}")]

    payload = {
        "key": key,
        "title": title,
        "install": install,
        "results": [dataclasses.asdict(r) for r in results],
    }
    data = json.dumps(payload)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(data)
    else:
        sys.stdout.write("\n@@DIAG@@" + data + "\n")
    return 0


# --- orchestrator ----------------------------------------------------------

_SYMBOL = {
    PASS: ("[OK]  ", _GREEN),
    SKIP: ("[SKIP]", _YELLOW),
    FAIL: ("[FAIL]", _RED),
}


def _print_result(res: Result) -> None:
    label, color = _SYMBOL[res.status]
    line = f"  {label} {res.name}"
    if res.detail:
        line += f" -- {res.detail}"
    print(_c(color, line))


def _run_module_subprocess(key: str, verbose: bool) -> List[Result]:
    timeout = _TIMEOUTS.get(key, _DEFAULT_TIMEOUT)
    tmp = tempfile.NamedTemporaryFile(prefix=f"diag_{key}_", suffix=".json", delete=False)
    tmp.close()
    cmd = [sys.executable, "-m", "nectar.diagnostics", "--worker", key, "--out", tmp.name]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        os.unlink(tmp.name)
        return [Result(f"{key}: module run", FAIL, f"timed out after {timeout}s")]

    payload = None
    try:
        with open(tmp.name, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        payload = None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if payload is None:
        detail = "worker produced no results"
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            detail = f"worker exited {proc.returncode}: {' | '.join(tail)}" if tail else detail
        return [Result(f"{key}: module run", FAIL, detail)]

    if verbose and (proc.stdout or proc.stderr):
        for stream in (proc.stdout, proc.stderr):
            for raw in (stream or "").splitlines():
                if raw.strip():
                    print(_c(_BLUE, f"      | {raw}"))

    return [Result(r["name"], r["status"], r.get("detail", "")) for r in payload["results"]]


def run(keys: Optional[List[str]] = None, *, verbose: bool = False) -> int:
    keys = keys or available_modules()
    print(_c(_PURPLE, "\n=== FUNCTIONAL VERIFICATION ===\n"))

    total = {PASS: 0, SKIP: 0, FAIL: 0}
    for key in keys:
        try:
            spec_title, spec_install = _module_header(key)
        except Exception:
            spec_title, spec_install = key, ""
        header = f"-- {spec_title}"
        if spec_install:
            header += f"  ({spec_install})"
        header += " --"
        print(_c(_PURPLE, header))

        results = _run_module_subprocess(key, verbose)
        counts = {PASS: 0, SKIP: 0, FAIL: 0}
        for res in results:
            _print_result(res)
            counts[res.status] = counts.get(res.status, 0) + 1
            total[res.status] = total.get(res.status, 0) + 1
        print(_c(_BLUE, f"   - {counts[PASS]} pass, {counts[SKIP]} skip, {counts[FAIL]} fail\n"))

    summary = f"=== RESULT: {total[PASS]} passed, {total[FAIL]} failed, {total[SKIP]} skipped ==="
    if total[FAIL] > 0:
        print(_c(_RED, summary))
        return 1
    print(_c(_GREEN, summary))
    return 0


def _module_header(key: str):
    """Read a module's title/install without running its checks (cheap import)."""
    try:
        spec = load_spec(key)
        return spec.title, spec.install
    except Exception:
        return key, ""


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nectar.diagnostics",
        description="Functional verification harness for the Nectar SDK.",
    )
    parser.add_argument(
        "modules", nargs="*", help="Subset of modules to run (default: all present)."
    )
    parser.add_argument("--list", action="store_true", help="List available modules and exit.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Stream each module's output.")
    parser.add_argument("--worker", metavar="KEY", help=argparse.SUPPRESS)
    parser.add_argument("--out", metavar="FILE", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.worker:
        return _worker(args.worker, args.out)

    if args.list:
        for key in available_modules():
            title, _ = _module_header(key)
            print(f"{key:14s} {title}")
        return 0

    keys = args.modules or None
    if keys:
        unknown = [k for k in keys if k not in available_modules()]
        if unknown:
            print(_c(_RED, f"Unknown module(s): {', '.join(unknown)}"))
            print(f"Available: {', '.join(available_modules())}")
            return 2

    return run(keys, verbose=args.verbose)
