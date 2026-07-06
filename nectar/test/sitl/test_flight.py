"""SITL / integration smoke flights, one per firmware + protocol.

Each case brings up the simulator (headless) via the ``sim_session`` fixture,
then flies a minimal real mission through the SDK: connect -> takeoff -> (move,
FCU only) -> land. This validates the vehicle core + the firmware/protocol link
(MAVROS, direct MAVLink, PX4 uXRCE-DDS, Crazyswarm2 sim) end to end.

Markers: ``sitl`` (the whole tier, deselected by default) plus a per-firmware
marker (``ardupilot`` / ``px4`` / ``crazyflie``). Select with, e.g.,
``pytest -m "sitl and px4"`` or by id ``-k px4-dds``. The deeper ArduPilot
navigation suite lives in ``examples/simulation/sitl_test.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402
import sim_helpers  # noqa: E402

pytestmark = pytest.mark.sitl

_PARAMS = [
    pytest.param(k, marks=getattr(pytest.mark, sim_helpers.SIM_SPECS[k].firmware), id=k)
    for k in sim_helpers.SIM_KEYS
]


@pytest.mark.parametrize("sim_session", _PARAMS, indirect=True)
def test_smoke_flight(sim_session):
    """Connect in sim, take off, move (FCU), and land for one firmware/protocol."""
    drone, spec = sim_session
    assert drone is not None, f"{spec.key}: SDK never connected to the simulator"

    assert drone.takeoff(altitude=spec.alt, precision=spec.precision, timeout=60.0), (
        f"{spec.key}: takeoff failed"
    )
    drone.delay(2.0)

    # FCU firmwares fly a short position move (Crazyflie sim only does takeoff/land
    # reliably -- velocity/arm paths are sim stubs).
    if spec.firmware != "crazyflie":
        from nectar.control import MoveReference, NavigationMethod

        assert drone.move_to(
            x=spec.move_x,
            reference=MoveReference.BODY,
            method=NavigationMethod.PID,
            precision=spec.precision,
            timeout=45.0,
        ), f"{spec.key}: move_to failed"
        drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

    landed = drone.land(timeout=45.0)
    assert landed is None or landed, f"{spec.key}: land failed"
