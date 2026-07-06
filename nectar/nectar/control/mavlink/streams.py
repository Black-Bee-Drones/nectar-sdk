"""MAVLink telemetry-rate setup for a :class:`MavlinkConnection`.

See https://mavlink.io/en/messages/common.html#MAV_CMD_SET_MESSAGE_INTERVAL.
"""

from typing import Dict, Optional

from pymavlink import mavutil

from nectar.control.mavlink.connection import MavlinkConnection

# Message name -> stream rate (Hz). Mirrors the set MAVROS' apm.launch enables:
# state/arming, attitude, EKF local pose, GPS fix + relative altitude/heading,
# rangefinder, and home position. ArduPilot Non-GPS guidance wants pose >= 4 Hz;
# we request higher so PID navigation has fresh feedback.
DEFAULT_STREAM_RATES: Dict[str, float] = {
    "HEARTBEAT": 1.0,
    "SYS_STATUS": 2.0,
    "ATTITUDE": 20.0,
    "GLOBAL_POSITION_INT": 10.0,
    "LOCAL_POSITION_NED": 20.0,
    "GPS_RAW_INT": 5.0,
    "RANGEFINDER": 10.0,
    "DISTANCE_SENSOR": 10.0,
    "VFR_HUD": 5.0,
    "HOME_POSITION": 1.0,
}


def _message_id(name: str) -> Optional[int]:
    """Resolve a MAVLink message name (e.g. ``"ATTITUDE"``) to its numeric id."""
    return getattr(mavutil.mavlink, f"MAVLINK_MSG_ID_{name}", None)


def request_message_intervals(
    connection: MavlinkConnection,
    rates: Optional[Dict[str, float]] = None,
) -> None:
    """
    Request per-message stream intervals via ``MAV_CMD_SET_MESSAGE_INTERVAL``.

    Parameters
    ----------
    connection : MavlinkConnection
        Connected endpoint to the FCU.
    rates : dict[str, float], optional
        ``{message_name: rate_hz}``. A rate ``<= 0`` disables the stream.
        Defaults to :data:`DEFAULT_STREAM_RATES`.
    """
    rates = rates if rates is not None else DEFAULT_STREAM_RATES
    master = connection.master

    for name, hz in rates.items():
        msg_id = _message_id(name)
        if msg_id is None:
            continue
        interval_us = -1.0 if hz <= 0 else float(int(1_000_000 / hz))
        with connection.send_lock:
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                float(msg_id),
                interval_us,
                0,
                0,
                0,
                0,
                0,
            )


def request_data_streams(connection: MavlinkConnection, rate_hz: float = 10.0) -> None:
    """
    Legacy ``REQUEST_DATA_STREAM`` fallback (all streams at ``rate_hz``).

    Use when an FCU does not honor ``SET_MESSAGE_INTERVAL``. ArduPilot 4.x
    supports the modern command, so this is rarely needed.
    """
    master = connection.master
    with connection.send_lock:
        master.mav.request_data_stream_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            int(rate_hz),
            1,
        )
