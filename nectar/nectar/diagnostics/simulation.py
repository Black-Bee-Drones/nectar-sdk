"""Simulation functional checks.

These need the simulation stack installed (``make sim-install``), so they
self-skip on a plain SDK install. Where Gazebo is present we step a headless
world to prove physics runs; SITL/PX4 presence is reported. A full autonomous
flight is the domain of ``examples/simulation/sitl_test.py`` (needs the two-
terminal sim running) and is surfaced as a documented manual step rather than
run here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec, Skip

_EMPTY_WORLD = (
    '<?xml version="1.0"?>\n'
    '<sdf version="1.8"><world name="diag_empty">'
    '<physics name="fast" type="ignored"><max_step_size>0.01</max_step_size>'
    "<real_time_factor>0</real_time_factor></physics>"
    "</world></sdf>\n"
)


def _ros_gz_packages() -> str:
    needed = ["ros_gz_sim", "ros_gz_bridge"]
    missing = [p for p in needed if not helpers.ros_package_present(p)]
    if missing:
        raise Skip(f"ros_gz packages absent: {missing} (make sim-install)")
    return "ros_gz_sim + ros_gz_bridge present"


def _gazebo_headless_step() -> str:
    gz = shutil.which("gz")
    if gz is None:
        raise Skip("gz not installed (make sim-install)")

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
        raise Fail("gz sim headless run timed out")
    finally:
        os.unlink(world)

    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["non-zero exit"]
        raise Fail(f"gz sim exited {proc.returncode}: {tail[0]}")
    return "gz sim stepped a headless world (5 iterations)"


def _ardupilot_sitl_present() -> str:
    if shutil.which("sim_vehicle.py") or os.path.isdir(os.path.expanduser("~/ardupilot")):
        return "ArduPilot SITL present"
    raise Skip("ArduPilot SITL not installed (make sim-install FIRMWARE=ardupilot)")


def _px4_sitl_present() -> str:
    if shutil.which("px4") or os.path.isdir(os.path.expanduser("~/PX4-Autopilot")):
        return "PX4 SITL present"
    raise Skip("PX4 SITL not installed (make sim-install FIRMWARE=px4)")


def _sitl_flight_suite() -> str:
    # A full autonomous flight needs a live two-terminal simulation; it is not
    # safe to auto-launch here. Always surfaced as a documented manual step.
    raise Skip(
        "full flight is manual: make sim-start + make sim-bridge, then "
        "python3 nectar/nectar/examples/simulation/sitl_test.py"
    )


MODULE = ModuleSpec(
    key="simulation",
    title="Simulation (Gazebo + SITL)",
    install="make sim-install",
    checks=[
        Check("ros_gz bridge packages", _ros_gz_packages),
        Check("Gazebo headless step", _gazebo_headless_step),
        Check("ArduPilot SITL present", _ardupilot_sitl_present),
        Check("PX4 SITL present", _px4_sitl_present),
        Check("SITL flight suite (sitl_test.py)", _sitl_flight_suite),
    ],
)
