"""Simulation functional tests.

These need the simulation stack installed (``make sim-install``), so they
self-skip on a plain SDK install. Where Gazebo is present we step a headless
world to prove physics runs; SITL presence is reported. A full autonomous flight
is the domain of ``examples/simulation/sitl_test.py`` (it needs the two-terminal
sim running) and is not auto-launched here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.sim

_EMPTY_WORLD = (
    '<?xml version="1.0"?>\n'
    '<sdf version="1.8"><world name="diag_empty">'
    '<physics name="fast" type="ignored"><max_step_size>0.01</max_step_size>'
    "<real_time_factor>0</real_time_factor></physics>"
    "</world></sdf>\n"
)


def _ros_package_present(name: str) -> bool:
    try:
        from ament_index_python.packages import get_package_prefix

        get_package_prefix(name)
        return True
    except Exception:
        return False


def test_ros_gz_packages():
    """The ros_gz bridge packages are discoverable via the ament index."""
    needed = ["ros_gz_sim", "ros_gz_bridge"]
    missing = [p for p in needed if not _ros_package_present(p)]
    if missing:
        pytest.skip(f"ros_gz packages absent: {missing} (make sim-install)")


def test_gazebo_headless_step():
    """Gazebo steps a headless empty world for a few iterations without error."""
    gz = shutil.which("gz")
    if gz is None:
        pytest.skip("gz not installed (make sim-install)")

    with tempfile.NamedTemporaryFile("w", suffix=".sdf", delete=False) as fh:
        fh.write(_EMPTY_WORLD)
        world = fh.name
    try:
        proc = subprocess.run(
            [gz, "sim", "-s", "-r", "--iterations", "5", world],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("gz sim headless run timed out")
    finally:
        os.unlink(world)

    assert proc.returncode == 0, (
        f"gz sim exited {proc.returncode}: {(proc.stderr or '').strip()[-200:]}"
    )


def test_ardupilot_sitl_present():
    """ArduPilot SITL is installed (sim_vehicle.py on PATH or ~/ardupilot present)."""
    if shutil.which("sim_vehicle.py") or os.path.isdir(os.path.expanduser("~/ardupilot")):
        return
    pytest.skip("ArduPilot SITL not installed (make sim-install FIRMWARE=ardupilot)")


def test_px4_sitl_present():
    """PX4 SITL is installed (px4 on PATH or ~/PX4-Autopilot present)."""
    if shutil.which("px4") or os.path.isdir(os.path.expanduser("~/PX4-Autopilot")):
        return
    pytest.skip("PX4 SITL not installed (make sim-install FIRMWARE=px4)")
