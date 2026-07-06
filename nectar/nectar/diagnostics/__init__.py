"""Nectar SDK environment doctor.

A read-only report of the current machine's ROS 2 environment, installed SDK
modules and optional dependencies, and available hardware/acceleration. Run with
``python3 -m nectar.diagnostics`` or ``make doctor``.

For a pass/fail check of the install, use ``make verify``; for functional
regression tests (real operations on synthetic inputs / loopbacks), the suite
lives under ``nectar/test/`` and runs via ``make verify-functional`` or
``colcon test``.
"""

from nectar.diagnostics.doctor import main

__all__ = ["main"]
