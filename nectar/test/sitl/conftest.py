"""Pytest fixtures for the SITL / integration test tier.

The ``sim_session`` fixture owns the full simulation lifecycle for one
firmware/protocol target: it brings the simulator up (headless), waits until the
SDK is connected and the vehicle is settled, yields a ``(drone, spec)`` pair, and
tears everything down with ``make sim-stop`` -- so a test body is just the flight.

``sys.path`` is extended with this directory so ``import sim_helpers`` resolves
on any pytest version (the module is named ``sim_helpers`` to avoid clashing with
the functional suite's ``test/helpers.py``).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402
import sim_helpers  # noqa: E402


@pytest.fixture
def sim_session(request):
    """Bring up the sim for ``request.param`` (a SIM_SPECS key); yield (drone, spec)."""
    spec = sim_helpers.SIM_SPECS[request.param]
    if spec.crazyflie and not sim_helpers.crazyflie_sim_available():
        pytest.skip("crazyflie_sim backend not installed (needs a Crazyswarm2 source build)")
    handles = []
    drone = None
    try:
        handles = sim_helpers.start_sim(spec)
        drone = sim_helpers.connect_drone(spec)
        yield (drone, spec)
    finally:
        sim_helpers.teardown(drone, handles, spec)
