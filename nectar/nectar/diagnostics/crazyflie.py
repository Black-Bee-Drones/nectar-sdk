"""Crazyflie / Crazyswarm2 functional checks.

Crazyswarm2 is an opt-in backend (``make drone-crazyflie``); when its packages
are absent every check self-skips. When present, the config/factory wiring is
verified. A full sim flight needs the ``crazyflie_server`` running with its
simulation backend, so it is surfaced as a documented manual step rather than
auto-launched.
"""

from __future__ import annotations

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec, Skip


def _crazyflie_present() -> bool:
    return helpers.ros_package_present("crazyflie") and helpers.ros_package_present(
        "crazyflie_interfaces"
    )


def _packages() -> str:
    if not _crazyflie_present():
        raise Skip("Crazyswarm2 packages not installed (make drone-crazyflie)")
    return "crazyflie + crazyflie_interfaces present"


def _config_and_factory() -> str:
    if not _crazyflie_present():
        raise Skip("Crazyswarm2 packages not installed (make drone-crazyflie)")
    from nectar.control.config import CrazyflieConfig
    from nectar.control.factory import DroneFactory

    if "crazyflie" not in DroneFactory.available_types():
        raise Fail("crazyflie not registered in DroneFactory")
    cfg = CrazyflieConfig()
    return f"CrazyflieConfig OK (uri={cfg.uri}), factory registered"


def _sim_flight() -> str:
    if not _crazyflie_present():
        raise Skip("Crazyswarm2 packages not installed (make drone-crazyflie)")
    # The sim backend requires a running crazyflie_server; not auto-launched.
    raise Skip(
        "sim flight is manual: ros2 launch crazyflie launch.py backend:=sim, then "
        "run a CrazyflieDrone takeoff/move/land"
    )


MODULE = ModuleSpec(
    key="crazyflie",
    title="Crazyflie / Crazyswarm2",
    install="make drone-crazyflie",
    checks=[
        Check("Crazyswarm2 packages", _packages),
        Check("Crazyflie config + factory", _config_and_factory),
        Check("Crazyswarm2 sim flight", _sim_flight),
    ],
)
