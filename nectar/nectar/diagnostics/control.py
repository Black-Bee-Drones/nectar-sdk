"""Control functional checks that need no flight controller.

Flight over MAVROS / PX4-DDS is validated through SITL (see the ``simulation``
module); here we exercise the pieces that stand alone: the factory/config layer,
the PID controller (a closed-loop step response to convergence), the geodesic
and frame-transform math, and the MAVLink transport's heartbeat handshake over a
UDP loopback (a stand-in FCU, no hardware).
"""

from __future__ import annotations

import math
import time

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec


def _factory_and_configs() -> str:
    from nectar.control.config import (
        BebopConfig,
        CrazyflieConfig,
        MavlinkConfig,
        MavrosConfig,
        Px4DdsConfig,
        Px4MavlinkConfig,
        Px4MavrosConfig,
    )
    from nectar.control.factory import DroneFactory

    expected = {"mavros", "mavlink", "px4", "px4_mavlink", "px4_dds", "bebop", "crazyflie"}
    types = set(DroneFactory.available_types())
    missing = expected - types
    if missing:
        raise Fail(f"factory missing drone types: {sorted(missing)}")

    # Every config dataclass must instantiate with defaults.
    configs = [
        MavrosConfig(),
        MavlinkConfig(),
        Px4MavrosConfig(),
        Px4MavlinkConfig(),
        Px4DdsConfig(),
        BebopConfig(),
        CrazyflieConfig(),
    ]
    return f"{len(types)} drone types registered, {len(configs)} configs instantiate"


def _pid_step_response() -> str:
    from nectar.control.pid import PIDController

    setpoint = 10.0
    pid = PIDController(
        kp=1.5,
        ki=0.2,
        kd=0.0,
        setpoint=setpoint,
        output_limits=(-50.0, 50.0),
        integral_limits=(-20.0, 20.0),
    )

    # Pure integrator plant driven by the controller output; uses the same
    # wall-clock dt the PID measures internally so the loop is consistent.
    value = 0.0
    last = None
    for _ in range(400):
        out = pid.update(value)
        now = time.time()
        dt = (now - last) if last is not None else 0.0
        last = now
        value += out * dt
        time.sleep(0.015)

    err = abs(value - setpoint)
    if err > 1.0:
        raise Fail(f"did not converge: final={value:.3f}, setpoint={setpoint} (err={err:.3f})")
    return f"converged to {value:.3f} (setpoint {setpoint})"


def _gps_math() -> str:
    helpers.require_module("geographiclib", "geographiclib not installed (control extra)")
    from nectar.utils.gps_calculate import GPSCalculate

    # One degree of latitude is ~111.2 km; due-north bearing is ~0 deg.
    dist = GPSCalculate.haversine(0.0, 0.0, 1.0, 0.0)
    if abs(dist - 111_195.0) > 2_000.0:
        raise Fail(f"haversine off: {dist:.0f} m (expected ~111195 m)")
    brg = GPSCalculate.bearing(0.0, 0.0, 1.0, 0.0)
    if not (brg < 2.0 or brg > 358.0):
        raise Fail(f"bearing off: {brg:.1f} deg (expected ~0)")
    return f"haversine={dist:.0f} m, bearing={brg:.1f} deg"


def _frame_transform() -> str:
    from nectar.utils.position_utils import PositionUtils

    # Forward (x) velocity in the takeoff frame, with the body yawed +90 deg,
    # must rotate into +y (left) in the body frame.
    vx, vy, vz = PositionUtils.transform_takeoff_to_body_velocities(
        1.0, 0.0, 0.0, current_yaw=math.radians(90.0), takeoff_yaw=0.0
    )
    if abs(vx) > 1e-6 or abs(vy - 1.0) > 1e-6:
        raise Fail(f"takeoff->body rotation wrong: ({vx:.3f}, {vy:.3f}, {vz:.3f})")
    return "takeoff->body velocity rotation correct"


def _mavlink_loopback() -> str:
    helpers.require_module("pymavlink", "pymavlink not installed (make python-sensors)")
    port = helpers.free_udp_port()
    fcu = helpers.FakeFcu(port).start()
    try:
        conn = helpers.mavlink_connection_to(port, heartbeat_timeout=8.0)
        if not conn.is_connected:
            raise Fail("connected but is_connected is False")
        target = conn.master.target_system
    finally:
        fcu.stop()
    return f"MAVLink heartbeat handshake OK (target_system={target})"


MODULE = ModuleSpec(
    key="control",
    title="Control",
    install="make python-control",
    checks=[
        Check("DroneFactory registry + configs", _factory_and_configs),
        Check("PID step response", _pid_step_response),
        Check("GPS distance/bearing", _gps_math),
        Check("frame transform (takeoff->body)", _frame_transform),
        Check("MAVLink loopback handshake", _mavlink_loopback),
    ],
)
