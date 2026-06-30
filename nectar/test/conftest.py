"""Pytest fixtures shared across the functional test suite.

Fixtures own the lifecycle of the things that are awkward to set up inline: the
SDK ROS runtime + a node, a loopback :class:`FakeFcu`, and an offscreen Qt app.
Each is function-scoped and torn down after the test.

The ``sys.path`` insert below puts ``test/`` on the path so ``import helpers``
resolves from any test module, without relying on the ``pythonpath`` ini option
(which needs pytest >= 7; Humble ships pytest 6).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers  # noqa: E402  (resolved via the sys.path insert above)
import pytest  # noqa: E402


@pytest.fixture
def ros_node():
    """Start the SDK executor, yield a registered node, then tear the runtime down."""
    helpers.ensure_ros()
    node = helpers.make_node("nectar_test")
    yield node
    helpers.shutdown_ros()


@pytest.fixture
def fake_fcu():
    """Yield a started loopback :class:`FakeFcu`; stop it on teardown."""
    port = helpers.free_udp_port()
    fcu = helpers.FakeFcu(port).start()
    yield fcu
    fcu.stop()


@pytest.fixture
def qt_app():
    """Yield a headless ``QApplication`` (offscreen platform), skipping if Qt is absent."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("MPLBACKEND", "Agg")
    pytest.importorskip("PySide6", reason="PySide6 not installed (make python-interface)")
    from PySide6.QtWidgets import QApplication

    try:
        app = QApplication.instance() or QApplication([])
    except Exception as exc:  # noqa: BLE001 - headless platform may be unavailable
        pytest.skip(f"Qt offscreen platform unavailable: {type(exc).__name__}")
    yield app
    app.processEvents()
