"""Interface functional test: build the Qt GUI offscreen.

Constructs the real ``NectarApp`` main window under the Qt ``offscreen``
platform (no display, no X server) and pumps the event loop, proving the GUI and
its tabs initialize. Self-skips when PySide6 is not installed (via the ``qt_app``
fixture).
"""

from __future__ import annotations

import os

import pytest

# Set before any Qt/matplotlib import so the headless platform is picked. The
# GUI imports mediapipe -> matplotlib; force a non-interactive backend.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

pytestmark = pytest.mark.interface


def test_qt_offscreen_build(qt_app):
    """NectarApp constructs offscreen with its control / vision / ROS tabs."""
    from nectar.interface import NectarApp

    window = NectarApp()
    try:
        for _ in range(5):
            qt_app.processEvents()
        missing = [
            a
            for a in ("_control_tab", "_vision_tab", "_ros_tab")
            if getattr(window, a, None) is None
        ]
        assert not missing, f"GUI tab(s) not constructed: {missing}"
    finally:
        window.close()
        qt_app.processEvents()
