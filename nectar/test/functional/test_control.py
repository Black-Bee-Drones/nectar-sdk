"""Control functional tests that need no flight controller.

Flight over MAVROS / PX4-DDS is validated through SITL (see ``test_simulation``);
here we exercise the pieces that stand alone: the factory/config layer, the PID
controller (a closed-loop step response to convergence), the geodesic and
frame-transform math, and the MAVLink transport's heartbeat handshake over a UDP
loopback (a stand-in FCU, no hardware).
"""

from __future__ import annotations

import math
import time

import pytest

pytestmark = pytest.mark.control


def test_factory_and_configs():
    """Every drone type is registered and each config dataclass instantiates with defaults."""
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
    assert expected <= types, f"factory missing drone types: {sorted(expected - types)}"

    for cfg in (
        MavrosConfig,
        MavlinkConfig,
        Px4MavrosConfig,
        Px4MavlinkConfig,
        Px4DdsConfig,
        BebopConfig,
        CrazyflieConfig,
    ):
        cfg()


def test_pid_step_response():
    """A PID driving a pure integrator plant converges to the setpoint."""
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
    assert err <= 1.0, f"did not converge: final={value:.3f}, setpoint={setpoint} (err={err:.3f})"


def test_gps_math():
    """Haversine distance and bearing match a known one-degree-north reference."""
    pytest.importorskip("geographiclib", reason="geographiclib not installed (control extra)")
    from nectar.utils.gps_calculate import GPSCalculate

    dist = GPSCalculate.haversine(0.0, 0.0, 1.0, 0.0)
    assert abs(dist - 111_195.0) <= 2_000.0, f"haversine off: {dist:.0f} m (expected ~111195 m)"
    brg = GPSCalculate.bearing(0.0, 0.0, 1.0, 0.0)
    assert brg < 2.0 or brg > 358.0, f"bearing off: {brg:.1f} deg (expected ~0)"


def test_frame_transform():
    """A forward takeoff-frame velocity rotates into +y when the body is yawed +90 deg."""
    from nectar.utils.position_utils import PositionUtils

    vx, vy, vz = PositionUtils.transform_takeoff_to_body_velocities(
        1.0, 0.0, 0.0, current_yaw=math.radians(90.0), takeoff_yaw=0.0
    )
    assert abs(vx) < 1e-6 and abs(vy - 1.0) < 1e-6, (
        f"rotation wrong: ({vx:.3f}, {vy:.3f}, {vz:.3f})"
    )


def test_is_airborne_prefers_fcu_landed_state():
    """Airborne detection follows MAVSDK: landed_state, then HEARTBEAT, then lidar.

    After touchdown the vehicle may still be armed with ON_GROUND / STANDBY;
    altitude alone must not force a false airborne skip.
    """
    from types import SimpleNamespace

    from nectar.control.vehicle.sequencer import FlightSequencer
    from nectar.control.vehicle.types import LandedState, VehicleState

    class _FakeDrone:
        def __init__(self) -> None:
            self.is_indoor = True
            self._armed = False
            self._transport = SimpleNamespace(
                state=VehicleState(),
                rangefinder=0.51,
                local_pose=None,
                rel_alt=None,
            )

        @property
        def is_armed(self):
            return self._armed

        def get_altitude(self, source=None):
            return self._transport.rangefinder

    drone = _FakeDrone()
    seq = FlightSequencer(drone)

    # Disarmed → never airborne.
    drone._armed = False
    drone._transport.state = VehicleState(
        armed=False,
        system_status=seq._MAV_STATE_STANDBY,
        landed_state=LandedState.ON_GROUND,
    )
    assert seq.is_airborne() is False

    # Primary: ON_GROUND while still armed (DISARM_DELAY window).
    drone._armed = True
    drone._transport.state = VehicleState(
        armed=True,
        system_status=seq._MAV_STATE_STANDBY,
        landed_state=LandedState.ON_GROUND,
    )
    assert seq.is_airborne() is False

    # Primary: IN_AIR / TAKEOFF / LANDING → airborne (ignore altitude).
    drone._transport.rangefinder = 0.0
    for ls in (LandedState.IN_AIR, LandedState.TAKEOFF, LandedState.LANDING):
        drone._transport.state = VehicleState(
            armed=True, system_status=seq._MAV_STATE_ACTIVE, landed_state=ls
        )
        assert seq.is_airborne() is True, ls

    # Tall pad with vision-like high reading is irrelevant when ON_GROUND.
    drone._transport.rangefinder = 1.5
    drone._transport.state = VehicleState(
        armed=True,
        system_status=seq._MAV_STATE_ACTIVE,
        landed_state=LandedState.ON_GROUND,
    )
    assert seq.is_airborne() is False

    # Fallback without landed_state: ACTIVE + lidar AGL below threshold → grounded.
    drone._transport.rangefinder = 0.13
    drone._transport.state = VehicleState(
        armed=True, system_status=seq._MAV_STATE_ACTIVE, landed_state=None
    )
    assert seq.is_airborne() is False

    # Fallback: ACTIVE + lidar above threshold → airborne.
    drone._transport.rangefinder = 1.5
    assert seq.is_airborne() is True

    # Fallback: ACTIVE + no lidar → trust ACTIVE.
    drone._transport.rangefinder = None
    assert seq.is_airborne() is True

    # Fallback: STANDBY without landed_state.
    drone._transport.rangefinder = 1.5
    drone._transport.state = VehicleState(
        armed=True, system_status=seq._MAV_STATE_STANDBY, landed_state=None
    )
    assert seq.is_airborne() is False

    # DDS-like status: rangefinder only.
    drone._transport.rangefinder = 0.51
    drone._transport.state = VehicleState(armed=True, system_status=2, landed_state=None)
    assert seq.is_airborne() is False
    drone._transport.rangefinder = 1.5
    assert seq.is_airborne() is True


def test_wait_landed_requires_fcu_standby():
    """Velocity touchdown alone is not enough; FCU ON_GROUND/STANDBY or disarm."""
    from types import SimpleNamespace

    from nectar.control.vehicle.sequencer import FlightSequencer
    from nectar.control.vehicle.types import LandedState, VehicleState

    class _Logger:
        def info(self, *_a, **_k):
            pass

        def warn(self, *_a, **_k):
            pass

    class _Node:
        def get_logger(self):
            return _Logger()

    class _FakeDrone:
        def __init__(self) -> None:
            self.is_indoor = True
            self._armed = True
            self._alt = 1.2
            self._node = _Node()
            self._transport = SimpleNamespace(
                state=VehicleState(
                    armed=True,
                    system_status=FlightSequencer._MAV_STATE_ACTIVE,
                    landed_state=LandedState.LANDING,
                ),
                rangefinder=1.2,
                local_pose=None,
                rel_alt=None,
            )

        @property
        def is_armed(self):
            return self._armed

        def get_altitude(self, source=None):
            return self._alt

    drone = _FakeDrone()
    seq = FlightSequencer(drone)
    seq._LAND_SETTLE_WINDOW = 0.2
    seq._SETTLE_POLL = 0.05

    # Touchdown while still LANDING / ACTIVE → timeout.
    drone._alt = 0.05
    drone._transport.rangefinder = 0.05
    assert seq.wait_landed(start_alt=1.2, timeout=0.8) is False

    # Touchdown then ON_GROUND → success.
    drone._transport.state = VehicleState(
        armed=True,
        system_status=FlightSequencer._MAV_STATE_STANDBY,
        landed_state=LandedState.ON_GROUND,
    )
    assert seq.wait_landed(start_alt=1.2, timeout=1.0) is True

    # Disarm during descent → success.
    drone._armed = True
    drone._alt = 0.8
    drone._transport.rangefinder = 0.8
    drone._transport.state = VehicleState(
        armed=True,
        system_status=FlightSequencer._MAV_STATE_ACTIVE,
        landed_state=LandedState.LANDING,
    )

    def _disarm_soon():
        time.sleep(0.15)
        drone._armed = False
        drone._transport.state = VehicleState(
            armed=False,
            system_status=FlightSequencer._MAV_STATE_STANDBY,
            landed_state=LandedState.ON_GROUND,
        )

    import threading

    threading.Thread(target=_disarm_soon, daemon=True).start()
    assert seq.wait_landed(start_alt=1.2, timeout=1.5) is True


def test_mavlink_loopback(fake_fcu):
    """The SDK MAVLink connection completes a heartbeat handshake with a loopback FCU."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers

    conn = helpers.mavlink_connection_to(fake_fcu.port, heartbeat_timeout=8.0)
    assert conn.is_connected, "connected but is_connected is False"
    assert conn.master.target_system >= 1
