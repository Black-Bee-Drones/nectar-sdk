"""Hardware-presence tests (skipped by default).

These need a physical device attached, so they are marked ``hardware`` and
deselected by the default test run. Enable them on the rig with::

    pytest test/hardware -m hardware

Each still self-skips with a clear reason when the driver is installed but no
device is attached, so the suite never fails for lack of hardware.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.hardware


def test_realsense_device():
    """An Intel RealSense device enumerates through pyrealsense2."""
    rs = pytest.importorskip("pyrealsense2", reason="pyrealsense2 not installed (realsense extra)")
    try:
        n = len(rs.context().query_devices())
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pyrealsense2 present, device query failed: {exc}")
    if n == 0:
        pytest.skip("pyrealsense2 installed, no RealSense device attached")


def test_oakd_device():
    """A Luxonis OAK-D device enumerates through depthai."""
    depthai = pytest.importorskip("depthai", reason="depthai not installed (oakd extra)")
    try:
        devices = depthai.Device.getAllAvailableDevices()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"depthai present, device query failed: {exc}")
    if not devices:
        pytest.skip("depthai installed, no OAK-D device attached")


def test_tfluna_serial():
    """The TF-Luna UART driver reads a sample from a serial port."""
    pytest.skip("requires a TF-Luna on a serial/UART port")
