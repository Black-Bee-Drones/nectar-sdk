"""Shared utilities for the functional diagnostics checks.

Imports are kept lazy (inside functions) so modules that do not touch ROS,
pymavlink or Qt pay nothing for them, and so an environment variable like
``QT_QPA_PLATFORM`` can be set before the first heavy import.
"""

from __future__ import annotations

import socket
import threading
import time
import uuid


def free_udp_port() -> int:
    """Return a currently-free UDP port on the loopback interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


# --- ROS 2 -----------------------------------------------------------------


def ensure_ros() -> None:
    """Start the SDK runtime executor (idempotent). Callbacks spin in the background."""
    import nectar

    if not nectar.is_initialized():
        nectar.init()


def make_node(prefix: str = "nectar_diag"):
    """Create a node and register it with the running SDK executor."""
    import rclpy

    import nectar

    node = rclpy.create_node(f"{prefix}_{uuid.uuid4().hex[:8]}")
    nectar.add_node(node)
    return node


def shutdown_ros() -> None:
    """Tear down the SDK runtime (also runs at process exit via atexit)."""
    import nectar

    if nectar.is_initialized():
        nectar.shutdown()


def publish_until(
    pub, msg, done: threading.Event, timeout: float = 5.0, rate_hz: float = 20.0
) -> bool:
    """Republish ``msg`` until ``done`` is set or ``timeout`` elapses.

    Repeated publishing absorbs DDS discovery latency between a fresh
    publisher and subscriber.
    """
    period = 1.0 / rate_hz
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pub.publish(msg)
        if done.wait(period):
            return True
    return done.is_set()


# --- MAVLink loopback ------------------------------------------------------


class FakeFcu:
    """A minimal MAVLink endpoint over UDP loopback, standing in for a real FCU.

    It sends periodic ``HEARTBEAT`` (as a quadrotor, so the SDK's connection
    handshake completes) and records every message the SDK sends back, so a
    test can assert that e.g. ``DISTANCE_SENSOR`` or ``VISION_POSITION_ESTIMATE``
    were emitted. Pair it with ``MavlinkConnection.connect("udpin:127.0.0.1:<port>")``.
    """

    def __init__(self, port: int, *, system: int = 1, component: int = 1) -> None:
        from pymavlink import mavutil

        self._mavutil = mavutil
        self._mav = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{port}",
            source_system=system,
            source_component=component,
        )
        self._stop = threading.Event()
        self._rx: list = []
        self._rx_lock = threading.Lock()
        self._tx_thread = threading.Thread(target=self._tx_loop, name="fakefcu-tx", daemon=True)
        self._rx_thread = threading.Thread(target=self._rx_loop, name="fakefcu-rx", daemon=True)

    def start(self) -> "FakeFcu":
        self._tx_thread.start()
        self._rx_thread.start()
        return self

    def _tx_loop(self) -> None:
        m = self._mavutil.mavlink
        while not self._stop.is_set():
            try:
                self._mav.mav.heartbeat_send(
                    m.MAV_TYPE_QUADROTOR, m.MAV_AUTOPILOT_GENERIC, 0, 0, m.MAV_STATE_ACTIVE
                )
            except Exception:
                pass
            self._stop.wait(0.1)

    def _rx_loop(self) -> None:
        while not self._stop.is_set():
            try:
                msg = self._mav.recv_match(blocking=True, timeout=0.2)
            except Exception:
                msg = None
            if msg is not None:
                with self._rx_lock:
                    self._rx.append(msg)

    def wait_for(self, msg_type: str, timeout: float = 3.0):
        """Return the first received message of ``msg_type`` within ``timeout``, else ``None``."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._rx_lock:
                for msg in self._rx:
                    if msg.get_type() == msg_type:
                        return msg
            time.sleep(0.02)
        return None

    def stop(self) -> None:
        self._stop.set()
        try:
            self._mav.close()
        except Exception:
            pass


def mavlink_connection_to(port: int, *, heartbeat_timeout: float = 5.0):
    """Open an SDK ``MavlinkConnection`` bound to a loopback port and complete the handshake.

    Assumes a :class:`FakeFcu` is already running on ``port``. Returns the
    connected ``MavlinkConnection``.
    """
    from nectar.control.mavlink import MavlinkConnection

    conn = MavlinkConnection(heartbeat_timeout=heartbeat_timeout)
    conn.connect(f"udpin:127.0.0.1:{port}")
    return conn


def ros_package_present(name: str) -> bool:
    """True if a ROS 2 package is discoverable via the ament index."""
    try:
        from ament_index_python.packages import get_package_prefix

        get_package_prefix(name)
        return True
    except Exception:
        return False


def require_module(name: str, hint: str = "") -> None:
    """Skip the current check (don't fail) when an optional dependency is absent."""
    import importlib.util

    if importlib.util.find_spec(name) is None:
        from nectar.diagnostics.runner import Skip

        raise Skip(hint or f"{name} not installed")
