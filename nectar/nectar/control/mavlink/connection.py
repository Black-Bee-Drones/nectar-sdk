"""Minimal pymavlink connection wrapper."""

import threading
import time
from typing import Optional

from pymavlink import mavutil

_NET_SCHEMES = ("tcp", "tcpin", "udp", "udpin", "udpout", "udpbcast")


def normalize_connection_string(device: str) -> str:
    """Accept both ``scheme://host:port`` and pymavlink's ``scheme:host:port``."""
    for scheme in _NET_SCHEMES:
        if device.startswith(f"{scheme}://"):
            return f"{scheme}:{device[len(scheme) + 3 :]}"
    return device


class MavlinkConnection:
    """
    Thin wrapper around ``pymavlink.mavutil.mavlink_connection``.

    The connection string and baud rate are passed to :meth:`connect`, not the
    constructor.

    Parameters
    ----------
    source_system : int, optional
        MAVLink system ID this connection presents itself as. Default 1
        (same system as the FCU; ArduPilot accepts companion-computer
        messages from the same system ID).
    source_component : int, optional
        MAVLink component ID. Default ``MAV_COMP_ID_ONBOARD_COMPUTER``
        (191), the ArduPilot convention for companion computers.
    heartbeat_timeout : float, optional
        Maximum seconds to wait for the first FCU heartbeat during
        :meth:`connect`. Default 30.

    Attributes
    ----------
    master : mavutil.mavfile
        Underlying pymavlink connection. Use ``master.mav.<message>_send(...)``
        to transmit. ``None`` until :meth:`connect` succeeds.

    Notes
    -----
    A single endpoint must have **one** RX reader (only the owning transport
    calls ``recv_match``) but may have **many** senders (setpoints, heartbeat,
    rangefinder, vision bridge). pymavlink's ``mav.*_send`` is not thread-safe,
    so every sender must serialize through :attr:`send_lock`.
    """

    def __init__(
        self,
        *,
        source_system: int = 1,
        source_component: int = mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
        heartbeat_timeout: float = 30.0,
    ) -> None:
        self._source_system = source_system
        self._source_component = source_component
        self._heartbeat_timeout = heartbeat_timeout
        self._send_lock = threading.Lock()
        self.master: Optional[mavutil.mavfile] = None

    @property
    def send_lock(self) -> threading.Lock:
        """Mutex serializing all transmits on this endpoint."""
        return self._send_lock

    @property
    def is_connected(self) -> bool:
        """Whether the heartbeat handshake completed."""
        return self.master is not None and self.master.target_system != 0

    def connect(self, device: str, baud: int = 921600) -> None:
        """
        Open the MAVLink endpoint and complete the heartbeat handshake.

        Blocks until the first non-GCS heartbeat arrives or until
        ``heartbeat_timeout``
        elapses.

        Parameters
        ----------
        device : str
            Connection string. Both ``tcp:host:port`` (pymavlink) and
            ``tcp://host:port`` (URL form) are accepted; serial uses a device
            path such as ``/dev/ttyUSB0``.
        baud : int, optional
            Serial baud rate. Ignored for non-serial connections.

        Raises
        ------
        TimeoutError
            If no FCU heartbeat is received within ``heartbeat_timeout``.
        """
        device = normalize_connection_string(device)
        self.master = mavutil.mavlink_connection(
            device,
            baud=baud,
            source_system=self._source_system,
            source_component=self._source_component,
        )

        if not self._await_heartbeat():
            raise TimeoutError(
                f"No FCU heartbeat received within {self._heartbeat_timeout}s on {device}"
            )

    def close(self) -> None:
        """Close the underlying pymavlink connection."""
        if self.master is not None:
            try:
                self.master.close()
            finally:
                self.master = None

    def _await_heartbeat(self) -> bool:
        """Wait for the first non-GCS HEARTBEAT to set target_system/component."""
        deadline = time.monotonic() + self._heartbeat_timeout
        skip_types = (
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
        )

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            msg = self.master.recv_match(
                type="HEARTBEAT", blocking=True, timeout=max(remaining, 0.1)
            )
            if msg is None:
                continue
            if msg.type in skip_types:
                continue

            self.master.target_system = msg.get_srcSystem()
            self.master.target_component = msg.get_srcComponent()
            return True

        return False
