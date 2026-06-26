"""Interface functional check: build the Qt GUI offscreen.

Constructs the real ``NectarApp`` main window under the Qt ``offscreen``
platform (no display, no X server) and pumps the event loop, proving the GUI and
its tabs initialize. Self-skips when PySide6 is not installed.
"""

from __future__ import annotations

import os

# Must be set before any Qt import so QApplication picks the headless platform.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The GUI imports mediapipe -> matplotlib; force a non-interactive backend so
# matplotlib does not try to load a Qt backend (headless, and avoids a
# matplotlib/PySide6 enum incompatibility on some setups).
os.environ.setdefault("MPLBACKEND", "Agg")

from nectar.diagnostics.runner import Check, Fail, ModuleSpec, Skip


def _qt_offscreen() -> str:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        raise Skip("PySide6 not installed (make python-interface)")

    try:
        app = QApplication.instance() or QApplication([])
    except Exception as exc:  # noqa: BLE001 - headless platform may be unavailable
        raise Skip(f"Qt offscreen platform unavailable: {type(exc).__name__}")

    from nectar.interface import NectarApp

    window = NectarApp()
    try:
        for _ in range(5):
            app.processEvents()
        missing = [
            a
            for a in ("_control_tab", "_vision_tab", "_ros_tab")
            if getattr(window, a, None) is None
        ]
        if missing:
            raise Fail(f"GUI tab(s) not constructed: {missing}")
    finally:
        window.close()
        app.processEvents()
    return "NectarApp built offscreen (control / vision / ROS tabs)"


MODULE = ModuleSpec(
    key="interface",
    title="Interface (Qt6)",
    install="make python-interface",
    checks=[
        Check("Qt GUI offscreen construct", _qt_offscreen),
    ],
)
