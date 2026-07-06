"""Nectar SDK environment doctor.

A read-only report of *this machine*: ROS 2 environment, which SDK modules and
optional dependencies are installed, and what hardware/acceleration is actually
available right now (RealSense, OAK-D, V4L cameras, CUDA). It answers "is my
install healthy and what can it do here?" -- the runtime companion to the
build-time ``make verify`` and the regression tests under ``test/``.

It performs no real operations and is safe to run anywhere. Heavy imports are
done lazily and guarded, so a missing optional dependency is reported, not
raised. Run with ``python3 -m nectar.diagnostics`` (or ``make doctor``).
"""

from __future__ import annotations

import glob
import importlib.metadata as _md
import importlib.util as _ilu
import os
import platform
import sys
from typing import Optional

_GREEN = "\033[0;32m"
_YELLOW = "\033[1;33m"
_BLUE = "\033[0;34m"
_PURPLE = "\033[0;35m"
_NC = "\033[0m"


def _color_enabled() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(color: str, text: str) -> str:
    return f"{color}{text}{_NC}" if _color_enabled() else text


def _present(module: str) -> bool:
    """True if an importable module exists, without importing it."""
    try:
        return _ilu.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _version(dist: str) -> str:
    try:
        return _md.version(dist)
    except _md.PackageNotFoundError:
        return "?"


def _section(title: str) -> None:
    print(_c(_PURPLE, f"\n-- {title} --"))


def _line(ok: Optional[bool], label: str, detail: str = "") -> None:
    """Print a status line; ``ok=None`` is informational (no mark)."""
    if ok is None:
        mark = _c(_BLUE, "  •   ")
    elif ok:
        mark = _c(_GREEN, "  [ok] ")
    else:
        mark = _c(_YELLOW, "  [--] ")
    line = f"{mark}{label}"
    if detail:
        line += f"  {detail}"
    print(line)


def _environment() -> None:
    _section("Environment")
    _line(None, "OS", f"{platform.system()} {platform.release()} ({platform.machine()})")
    _line(None, "Python", platform.python_version())
    _line(None, "ROS distro", os.environ.get("ROS_DISTRO", "(not sourced)"))
    _line(None, "RMW", os.environ.get("RMW_IMPLEMENTATION", "(default)"))
    _line(None, "ROS_DOMAIN_ID", os.environ.get("ROS_DOMAIN_ID", "(unset -> 0)"))
    venv = os.environ.get("VIRTUAL_ENV")
    _line(None, "venv", venv or "(none active)")


def _sdk() -> None:
    _section("Nectar SDK")
    _line(_present("nectar"), "nectar", f"v{_version('nectar-sdk')}")
    for mod in (
        "nectar.control",
        "nectar.vision",
        "nectar.sensors",
        "nectar.ai",
        "nectar.interface",
    ):
        _line(_present(mod), mod)


def _optional_deps() -> None:
    _section("Optional dependencies")
    groups = {
        "control": [
            ("pygeodesy", "pygeodesy"),
            ("transforms3d", "transforms3d"),
            ("sklearn", "scikit-learn"),
        ],
        "sensors": [("serial", "pyserial"), ("pymavlink", "pymavlink")],
        "vision": [
            ("mediapipe", "mediapipe"),
            ("depthai", "depthai"),
            ("pyrealsense2", "pyrealsense2"),
        ],
        "interface": [("PySide6", "PySide6"), ("pyqtgraph", "pyqtgraph")],
        "ai": [
            ("torch", "torch"),
            ("ultralytics", "ultralytics"),
            ("transformers", "transformers"),
        ],
    }
    for group, mods in groups.items():
        installed = [(m, d) for m, d in mods if _present(m)]
        if not installed:
            _line(False, group, "(not installed)")
            continue
        detail = ", ".join(f"{m.split('.')[0]} {_version(d)}" for m, d in installed)
        _line(True, group, detail)


def _devices() -> None:
    _section("Devices & acceleration")

    v4l = sorted(glob.glob("/dev/video*"))
    _line(bool(v4l), "V4L cameras", ", ".join(v4l) if v4l else "(none at /dev/video*)")

    if _present("pyrealsense2"):
        try:
            import pyrealsense2 as rs

            n = len(rs.context().query_devices())
            _line(n > 0, "RealSense", f"{n} device(s)" if n else "driver ok, no device")
        except Exception as exc:  # noqa: BLE001 - report, never raise
            _line(False, "RealSense", f"query failed: {type(exc).__name__}")
    else:
        _line(False, "RealSense", "pyrealsense2 not installed")

    if _present("depthai"):
        try:
            import depthai

            devs = depthai.Device.getAllAvailableDevices()
            _line(bool(devs), "OAK-D", f"{len(devs)} device(s)" if devs else "driver ok, no device")
        except Exception as exc:  # noqa: BLE001 - report, never raise
            _line(False, "OAK-D", f"query failed: {type(exc).__name__}")
    else:
        _line(False, "OAK-D", "depthai not installed")

    if _present("torch"):
        try:
            import torch

            if torch.cuda.is_available():
                _line(True, "CUDA", f"{torch.cuda.get_device_name(0)} (torch {torch.__version__})")
            else:
                _line(False, "CUDA", f"no usable GPU (torch {torch.__version__})")
        except Exception as exc:  # noqa: BLE001 - report, never raise
            _line(False, "CUDA", f"torch import failed: {type(exc).__name__}")
    else:
        _line(False, "CUDA", "torch not installed")


def main(argv: Optional[list] = None) -> int:
    """Print the environment report. Returns non-zero only if the SDK is unimportable."""
    print(_c(_PURPLE, "\n=== NECTAR DOCTOR ==="))
    _environment()
    _sdk()
    _optional_deps()
    _devices()
    print(_c(_BLUE, "\nThis is an environment report. For a pass/fail check of the install run"))
    print(
        _c(_BLUE, "`make verify`; for functional regression tests run `make verify-functional`.\n")
    )
    return 0 if _present("nectar") else 1


if __name__ == "__main__":
    sys.exit(main())
