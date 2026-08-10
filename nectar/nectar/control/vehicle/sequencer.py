"""Takeoff/land settle detection for multicopter vehicles."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Tuple

from nectar.utils.log import ARROW

if TYPE_CHECKING:
    from nectar.control.vehicle.drone import VehicleDrone


class FlightSequencer:
    """Liftoff/touchdown detection with size-agnostic velocity gating."""

    # MAVLink HEARTBEAT.system_status. ArduCopter reports STANDBY when
    # land_complete and ACTIVE once flying (see GCS_MAVLINK_Copter).
    _MAV_STATE_STANDBY = 3
    _MAV_STATE_ACTIVE = 4
    # Altitude fallback only (when FCU landed/flying state is unavailable).
    # Must clear typical grounded readings: body/mount height, elevated pads,
    # and vision Z relative to a lower takeoff origin.
    _AIRBORNE_THRESHOLD = 0.9  # m

    # Takeoff settle. Velocity-based detection absorbs sensor spikes that
    # would otherwise reset an absolute-spread check on real airframes.
    _SPIN_UP_DELAY = 2.7  # s, post-arm delay before takeoff command
    _LIFTOFF_DELTA = 0.08  # m, altitude rise required to consider lifted
    _SETTLE_WINDOW = 0.8  # s, rolling window for vertical-velocity check
    _SETTLE_VELOCITY = 0.25  # m/s, |dz/dt| below which the hover is declared settled
    _SETTLE_POLL = 0.1  # s, poll period for settle/landed loops
    _SETTLE_LOG_INTERVAL = 1.0  # s, throttle for takeoff climb progress logs
    _SETTLE_ALT_TOLERANCE = 0.5  # m, max altitude band below target for settle
    _SETTLE_ALT_FRACTION = 0.3  # fraction of climb used as the settle band

    # Landing settle (velocity-based, drone-size agnostic)
    _LANDED_THRESHOLD = 0.3  # m, absolute "already low" fallback for descent gate
    _LAND_SETTLE_WINDOW = 1.2  # s, rolling window for descent velocity
    _LAND_STOP_VELOCITY = 0.05  # m/s, descent rate below which touchdown is declared

    def __init__(self, drone: "VehicleDrone") -> None:
        self._drone = drone

    @property
    def spin_up_delay(self) -> float:
        """Post-arm delay before issuing the takeoff command."""
        return self._SPIN_UP_DELAY

    def is_airborne(self) -> bool:
        """True when the vehicle is flying (not on the ground).

        Prefers FCU landed/flying state from ``HEARTBEAT.system_status`` when
        it carries real MAVLink semantics (ArduPilot/PX4 MAVLink): STANDBY
        means on the ground, ACTIVE means in flight. Disarmed is never
        airborne. Altitude is only a fallback for transports that do not
        expose that status (e.g. PX4 DDS maps arming_state into the same
        field); the fallback uses a single threshold for every source so a
        grounded rangefinder reading body height or an elevated pad cannot
        false-trigger the takeoff short-circuit.
        """
        drone = self._drone
        if drone.is_armed is False:
            return False

        status = drone._transport.state.system_status
        if status == self._MAV_STATE_STANDBY:
            return False
        if status == self._MAV_STATE_ACTIVE:
            return True

        transport = drone._transport
        thr = self._AIRBORNE_THRESHOLD

        rng = transport.rangefinder
        if rng is not None:
            return rng > thr

        local = transport.local_pose
        if local is not None and local.position.z > thr:
            return True
        if not drone.is_indoor:
            rel = transport.rel_alt
            if rel is not None and rel > thr:
                return True
        return False

    def wait_landed(self, start_alt: float, timeout: float) -> bool:
        """
        Wait for touchdown after a land command.

        Returns when the drone has descended from ``start_alt`` AND its descent
        velocity over ``_LAND_SETTLE_WINDOW`` has dropped below
        ``_LAND_STOP_VELOCITY``, or when the FCU disarms.

        Returns
        -------
        bool
            True on touchdown or disarm, False on timeout.
        """
        drone = self._drone
        deadline = time.time() + timeout
        last_alt = drone.get_altitude() or start_alt
        history: list = [(time.time(), last_alt)]
        descended = False
        while time.time() < deadline:
            time.sleep(self._SETTLE_POLL)
            if not drone.is_armed:
                return True
            now = time.time()
            alt = drone.get_altitude() or last_alt
            if start_alt - alt > self._LIFTOFF_DELTA or alt < self._LANDED_THRESHOLD:
                descended = True
            cutoff = now - self._LAND_SETTLE_WINDOW
            # Keep the newest sample at least one window old so window_dt spans
            # the full duration (history[0] <= cutoff <= history[1]).
            while len(history) > 1 and history[1][0] <= cutoff:
                history.pop(0)
            window_dt = now - history[0][0]
            if descended and window_dt >= self._LAND_SETTLE_WINDOW:
                descent_rate = (history[0][1] - alt) / window_dt
                if descent_rate < self._LAND_STOP_VELOCITY:
                    return True
            history.append((now, alt))
            last_alt = alt
        return False

    def wait_takeoff_settle(
        self, start_alt: float, target_alt: float, timeout: float
    ) -> Tuple[bool, float]:
        """Wait for the climb to reach the commanded altitude and stabilize.

        Lifted when altitude rises by ``_LIFTOFF_DELTA`` from ``start_alt``.
        Settled when the drone is within ``_settle_band`` of ``target_alt`` and
        the mean vertical velocity over ``_SETTLE_WINDOW`` falls below
        ``_SETTLE_VELOCITY``. The target-proximity gate prevents a slow initial
        liftoff (low velocity, still near the ground) from being mistaken for a
        completed takeoff. Aborts on disarm.

        Returns
        -------
        tuple of (bool, float)
            ``(lifted_off, current_altitude)``.
        """
        drone = self._drone
        logger = drone._node.get_logger()
        deadline = time.time() + timeout
        last_alt = drone.get_altitude() or start_alt
        history: list = [(time.time(), last_alt)]
        lifted = False
        floor = target_alt - self._settle_band(target_alt - start_alt)
        next_log = time.time() + self._SETTLE_LOG_INTERVAL
        while time.time() < deadline:
            time.sleep(self._SETTLE_POLL)
            if not drone.is_armed:
                break
            now = time.time()
            alt = drone.get_altitude() or last_alt
            if alt - start_alt > self._LIFTOFF_DELTA:
                lifted = True
            cutoff = now - self._SETTLE_WINDOW
            # Keep the newest sample at least one window old so window_dt spans
            # the full duration (history[0] <= cutoff <= history[1]).
            while len(history) > 1 and history[1][0] <= cutoff:
                history.pop(0)
            window_dt = now - history[0][0]
            velocity = (alt - history[0][1]) / window_dt if window_dt > 0 else 0.0
            if now >= next_log:
                logger.info(
                    f"{ARROW} Takeoff climb: {alt:.2f}m "
                    f"(gain {alt - start_alt:+.2f}m, vz {velocity:+.2f}m/s)"
                )
                next_log = now + self._SETTLE_LOG_INTERVAL
            settled = (
                lifted
                and alt >= floor
                and window_dt >= self._SETTLE_WINDOW
                and abs(velocity) < self._SETTLE_VELOCITY
            )
            if settled:
                return True, alt
            history.append((now, alt))
            last_alt = alt
        return lifted, last_alt

    def _settle_band(self, climb: float) -> float:
        """Altitude tolerance below target for declaring the takeoff settled."""
        return min(self._SETTLE_ALT_TOLERANCE, self._SETTLE_ALT_FRACTION * climb)
