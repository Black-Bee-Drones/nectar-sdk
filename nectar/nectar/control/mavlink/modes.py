"""Firmware-specific flight-mode handling for :class:`PymavlinkTransport`.

The transport owns all wire plumbing (connection, RX/TX, telemetry, setpoints);
only the flight-mode representation differs per autopilot:

* ArduPilot encodes a mode as a single ``custom_mode`` integer looked up from
  pymavlink's ``mode_mapping()`` and sent via the ``SET_MODE`` message.
* PX4 encodes a mode as a ``(main_mode, sub_mode)`` pair sent via
  ``MAV_CMD_DO_SET_MODE`` (see :mod:`nectar.control.px4.modes`).

A :class:`MavlinkModeCodec` isolates that difference so one transport serves
both firmwares, mirroring how ``MavrosTransport`` already serves ArduPilot and
PX4. The transport injects a codec (defaulting to :class:`ArduPilotModeCodec`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pymavlink import mavutil

_M = mavutil.mavlink


class MavlinkModeCodec(ABC):
    """Encode/decode flight modes for a specific autopilot over MAVLink."""

    @abstractmethod
    def set_mode(self, transport, mode: str) -> bool:
        """Command the FCU into ``mode``; ``True`` if sent/accepted."""

    @abstractmethod
    def decode_mode(self, msg) -> str:
        """Map a ``HEARTBEAT`` message to a flight-mode name."""

    @property
    @abstractmethod
    def land_mode(self) -> str:
        """Mode name that lands at the current position."""

    def is_guided(self, mode: str) -> bool:
        """Whether ``mode`` is the offboard/guided external-control mode."""
        return False


class ArduPilotModeCodec(MavlinkModeCodec):
    """ArduPilot modes: pymavlink ``mode_mapping()`` + ``SET_MODE``."""

    def set_mode(self, transport, mode: str) -> bool:
        master = transport.connection.master
        mapping = master.mode_mapping() or {}
        mode_id = mapping.get(mode)
        if mode_id is None:
            transport.node.get_logger().error(
                f"Unknown flight mode '{mode}'. Available: {sorted(mapping)}"
            )
            return False
        with transport.connection.send_lock:
            master.mav.set_mode_send(
                master.target_system, _M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id
            )
        return True

    def decode_mode(self, msg) -> str:
        return mavutil.mode_string_v10(msg)

    @property
    def land_mode(self) -> str:
        return "LAND"

    def is_guided(self, mode: str) -> bool:
        return mode == "GUIDED"
