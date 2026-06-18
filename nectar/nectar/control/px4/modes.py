"""PX4 flight-mode encoding shared by the PX4 transports.

PX4 represents a flight mode as a ``(main_mode, sub_mode)`` pair:

* Over MAVLink it is set with ``MAV_CMD_DO_SET_MODE`` (param2=main, param3=sub)
  and reported in the ``HEARTBEAT.custom_mode`` field as
  ``(main << 16) | (sub << 24)``.
* Over uXRCE-DDS the same pair is sent via ``VehicleCommand`` 176.

Source: PX4 ``px4_custom_mode.h`` (``PX4_CUSTOM_MAIN_MODE_*`` /
``PX4_CUSTOM_SUB_MODE_AUTO_*``).
"""

from __future__ import annotations

# Flight-mode name -> (main_mode, sub_mode).
MODE_TO_PX4 = {
    "MANUAL": (1, 0),
    "ALTCTL": (2, 0),
    "POSCTL": (3, 0),
    "AUTO.TAKEOFF": (4, 2),
    "AUTO.LOITER": (4, 3),
    "AUTO.MISSION": (4, 4),
    "AUTO.RTL": (4, 5),
    "AUTO.LAND": (4, 6),
    "ACRO": (5, 0),
    "OFFBOARD": (6, 0),
    "STABILIZED": (7, 0),
}

# HOLD is PX4's common alias for AUTO.LOITER.
MODE_TO_PX4["HOLD"] = MODE_TO_PX4["AUTO.LOITER"]

# Reverse lookup for decoding HEARTBEAT.custom_mode (canonical names only).
_PX4_TO_MODE = {pair: name for name, pair in MODE_TO_PX4.items() if name != "HOLD"}


def px4_mode_name(custom_mode: int) -> str:
    """Decode a ``HEARTBEAT.custom_mode`` into a PX4 mode name.

    Returns ``"UNKNOWN"`` when the ``(main, sub)`` pair is not recognized.
    """
    main = (int(custom_mode) >> 16) & 0xFF
    sub = (int(custom_mode) >> 24) & 0xFF
    return _PX4_TO_MODE.get((main, sub), "UNKNOWN")
