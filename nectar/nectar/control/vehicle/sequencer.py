"""Takeoff/land settle detection for multicopter vehicles."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Tuple

from nectar.control.vehicle.types import LandedState
from nectar.utils.log import ARROW, OK

if TYPE_CHECKING:
    from nectar.control.vehicle.drone import VehicleDrone


class FlightSequencer:
    """Liftoff/touchdown settle and FCU landed-state gating.

    Airborne / landed priority matches MAVSDK: ``EXTENDED_SYS_STATE.landed_state``
    first, then ``HEARTBEAT.system_status``, then rangefinder AGL.
    https://mavsdk.mavlink.io/ — ``TelemetryImpl::process_extended_sys_state``.
    """

    _MAV_STATE_STANDBY = 3
    _MAV_STATE_ACTIVE = 4
    _AIRBORNE_THRESHOLD = 0.9  # m; lidar-only when landed_state unknown

    _SPIN_UP_DELAY = 2.7  # s
    _LIFTOFF_DELTA = 0.08  # m
    _SETTLE_WINDOW = 0.8  # s
    _SETTLE_VELOCITY = 0.25  # m/s
    _SETTLE_POLL = 0.1  # s
    _SETTLE_LOG_INTERVAL = 1.0  # s
    _SETTLE_ALT_TOLERANCE = 0.5  # m
    _SETTLE_ALT_FRACTION = 0.3

    _LANDED_THRESHOLD = 0.3  # m
    _LAND_SETTLE_WINDOW = 1.2  # s
    _LAND_STOP_VELOCITY = 0.05  # m/s

    _IN_AIR_STATES = frozenset({LandedState.IN_AIR, LandedState.TAKEOFF, LandedState.LANDING})

    def __init__(self, drone: "VehicleDrone") -> None:
        self._drone = drone

    @property
    def spin_up_delay(self) -> float:
        """Post-arm delay before issuing the takeoff command."""
        return self._SPIN_UP_DELAY

    def is_fcu_landed(self) -> bool:
        """True when the FCU reports on-ground, or landed state is unavailable.

        Priority:

        1. Disarmed → landed.
        2. ``landed_state == ON_GROUND`` → landed.
        3. ``landed_state`` in {IN_AIR, TAKEOFF, LANDING} → not landed.
        4. Fallback: ``HEARTBEAT.system_status == STANDBY``.
        5. Transports without MAVLink flight state (e.g. PX4 DDS) → true after
           velocity touchdown so land does not hang.
        """
        drone = self._drone
        if drone.is_armed is False:
            return True

        landed = drone._transport.state.landed_state
        if landed == LandedState.ON_GROUND:
            return True
        if landed in self._IN_AIR_STATES:
            return False

        status = drone._transport.state.system_status
        if status == self._MAV_STATE_STANDBY:
            return True
        if status == self._MAV_STATE_ACTIVE:
            return False
        # No usable FCU flight/landed signal (e.g. PX4 DDS arming_state mapping).
        return True

    def is_airborne(self) -> bool:
        """True when the vehicle is flying (not on the ground).

        Priority (same mapping as MAVSDK ``Telemetry::in_air``):

        1. Disarmed → not airborne.
        2. ``EXTENDED_SYS_STATE.landed_state`` when known:
           ON_GROUND → false; IN_AIR / TAKEOFF / LANDING → true.
        3. Else ``HEARTBEAT.system_status``: STANDBY → false; ACTIVE → true,
           unless a **rangefinder** reading is available and below
           ``_AIRBORNE_THRESHOLD`` (AGL-only race net; never vision/rel_alt).
        4. Else rangefinder AGL vs threshold, or false if no rangefinder.
        """
        drone = self._drone
        if drone.is_armed is False:
            return False

        landed = drone._transport.state.landed_state
        if landed == LandedState.ON_GROUND:
            return False
        if landed in self._IN_AIR_STATES:
            return True

        status = drone._transport.state.system_status
        rng = drone._transport.rangefinder
        thr = self._AIRBORNE_THRESHOLD

        if status == self._MAV_STATE_STANDBY:
            return False
        if status == self._MAV_STATE_ACTIVE:
            if rng is not None and rng < thr:
                return False
            return True

        if rng is not None:
            return rng > thr
        return False

    def wait_landed(self, start_alt: float, timeout: float) -> bool:
        """
        Wait for touchdown after a land command, then FCU landed confirmation.

        1. Velocity touchdown: descended from ``start_alt`` and descent rate
           over ``_LAND_SETTLE_WINDOW`` below ``_LAND_STOP_VELOCITY``, or
           disarmed.
        2. FCU confirm: ``landed_state == ON_GROUND``, or ``STANDBY``, or
           disarmed. Does not wait for ``DISARM_DELAY``.

        Returns
        -------
        bool
            True when touchdown and FCU landed/disarm are confirmed, False on
            timeout.
        """
        drone = self._drone
        logger = drone._node.get_logger()
        deadline = time.time() + timeout
        last_alt = drone.get_altitude() or start_alt
        history: list = [(time.time(), last_alt)]
        descended = False
        touchdown = False

        while time.time() < deadline:
            time.sleep(self._SETTLE_POLL)
            if not drone.is_armed:
                logger.info(f"{OK} Land confirmed: disarmed")
                return True

            now = time.time()
            alt = drone.get_altitude() or last_alt
            if start_alt - alt > self._LIFTOFF_DELTA or alt < self._LANDED_THRESHOLD:
                descended = True
            cutoff = now - self._LAND_SETTLE_WINDOW
            while len(history) > 1 and history[1][0] <= cutoff:
                history.pop(0)
            window_dt = now - history[0][0]
            if not touchdown and descended and window_dt >= self._LAND_SETTLE_WINDOW:
                descent_rate = (history[0][1] - alt) / window_dt
                if descent_rate < self._LAND_STOP_VELOCITY:
                    touchdown = True
                    logger.info(f"{ARROW} Touchdown at {alt:.2f}m, waiting for FCU landed state")
            history.append((now, alt))
            last_alt = alt

            if touchdown and self.is_fcu_landed():
                state = drone._transport.state
                logger.info(
                    f"{OK} Land confirmed: landed_state={state.landed_state} "
                    f"status={state.system_status} (armed={drone.is_armed})"
                )
                return True

        return False

    def wait_takeoff_settle(
        self, start_alt: float, target_alt: float, timeout: float
    ) -> Tuple[bool, float]:
        """Wait for the climb to reach the commanded altitude and stabilize.

        Lifted when altitude rises by ``_LIFTOFF_DELTA`` from ``start_alt``.
        Settled when the drone is within ``_settle_band`` of ``target_alt`` and
        the mean vertical velocity over ``_SETTLE_WINDOW`` falls below
        ``_SETTLE_VELOCITY``. Aborts on disarm.

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
