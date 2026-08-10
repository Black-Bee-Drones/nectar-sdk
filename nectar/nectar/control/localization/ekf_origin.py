"""Optional ``SET_GPS_GLOBAL_ORIGIN`` helpers for the vision-pose bridge.

Origin only — Home is left to the FCU (ArduPilot initializes it after origin /
at arm). See localization README → EKF origin.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from rclpy.node import Node

    from nectar.control.mavlink.connection import MavlinkConnection

# Default global position for EKF origin
DEFAULT_ORIGIN_LAT = -22.41434308754571
DEFAULT_ORIGIN_LON = -45.44843145453864
DEFAULT_ORIGIN_ALT_M = 0.0


def origin_to_mavlink(lat_deg: float, lon_deg: float, alt_m: float) -> Tuple[int, int, int]:
    """Pack WGS84 degrees / meters into MAVLink ``SET_GPS_GLOBAL_ORIGIN`` fields."""
    return (
        int(round(lat_deg * 1e7)),
        int(round(lon_deg * 1e7)),
        int(round(alt_m * 1000.0)),
    )


def send_mavlink_origin(
    connection: "MavlinkConnection",
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
) -> None:
    """Send ``SET_GPS_GLOBAL_ORIGIN`` once on an open pymavlink link."""
    if connection.master is None:
        raise RuntimeError("MAVLink connection is not open")
    lat_e7, lon_e7, alt_mm = origin_to_mavlink(lat_deg, lon_deg, alt_m)
    with connection.send_lock:
        connection.master.mav.set_gps_global_origin_send(
            connection.master.target_system,
            lat_e7,
            lon_e7,
            alt_mm,
        )


def origin_already_set_mavlink(
    connection: "MavlinkConnection",
    timeout_s: float,
) -> bool:
    """True if ``GPS_GLOBAL_ORIGIN`` arrives within ``timeout_s``."""
    if connection.master is None:
        return False
    # Ask the FCU to (re)emit origin if it already has one.
    with connection.send_lock:
        connection.master.mav.command_long_send(
            connection.master.target_system,
            connection.master.target_component,
            512,  # MAV_CMD_REQUEST_MESSAGE
            0,
            49,  # MAVLINK_MSG_ID_GPS_GLOBAL_ORIGIN
            0,
            0,
            0,
            0,
            0,
            0,
        )
    deadline = time.monotonic() + max(timeout_s, 0.0)
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        msg = connection.master.recv_match(
            type="GPS_GLOBAL_ORIGIN",
            blocking=True,
            timeout=max(remaining, 0.05),
        )
        if msg is not None:
            return True
    return False


def send_mavros_origin(
    node: "Node",
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
    *,
    namespace: str = "mavros",
) -> None:
    """Publish ``/mavros/global_position/set_gp_origin`` (``GeoPointStamped``)."""
    from geographic_msgs.msg import GeoPointStamped

    topic = f"/{namespace.strip('/')}/global_position/set_gp_origin"
    pub = node.create_publisher(GeoPointStamped, topic, 1)
    # Brief settle so MAVROS can subscribe before the single publish.
    time.sleep(0.2)
    msg = GeoPointStamped()
    msg.header.stamp = node.get_clock().now().to_msg()
    msg.header.frame_id = "map"
    msg.position.latitude = float(lat_deg)
    msg.position.longitude = float(lon_deg)
    msg.position.altitude = float(alt_m)
    pub.publish(msg)
    pub.publish(msg)


def origin_already_set_mavros(
    node: "Node",
    timeout_s: float,
    *,
    namespace: str = "mavros",
) -> bool:
    """True if ``/mavros/global_position/gp_origin`` is received within ``timeout_s``."""
    from geographic_msgs.msg import GeoPointStamped

    topic = f"/{namespace.strip('/')}/global_position/gp_origin"
    got = {"ok": False}

    def _on_msg(_msg: GeoPointStamped) -> None:
        got["ok"] = True

    sub = node.create_subscription(GeoPointStamped, topic, _on_msg, 10)
    deadline = time.monotonic() + max(timeout_s, 0.0)
    while time.monotonic() < deadline and not got["ok"]:
        # Caller spins; here we only sleep while the node's executor may be
        # shared. Prefer a local spin when available.
        try:
            import rclpy

            rclpy.spin_once(node, timeout_sec=0.05)
        except Exception:
            time.sleep(0.05)
    node.destroy_subscription(sub)
    return bool(got["ok"])


def send_dds_origin(
    node: "Node",
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
    *,
    px4_namespace: str = "",
) -> None:
    """Send PX4 ``VEHICLE_CMD_SET_GPS_GLOBAL_ORIGIN`` over uXRCE-DDS."""
    from px4_msgs.msg import VehicleCommand
    from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

    ns = px4_namespace.rstrip("/")
    topic = f"{ns}/fmu/in/vehicle_command" if ns else "/fmu/in/vehicle_command"
    qos = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
    )
    pub = node.create_publisher(VehicleCommand, topic, qos)
    time.sleep(0.1)
    msg = VehicleCommand()
    msg.command = int(VehicleCommand.VEHICLE_CMD_SET_GPS_GLOBAL_ORIGIN)
    msg.param5 = float(lat_deg)
    msg.param6 = float(lon_deg)
    msg.param7 = float(alt_m)
    msg.target_system = 1
    msg.target_component = 1
    msg.source_system = 1
    msg.source_component = 1
    msg.from_external = True
    msg.timestamp = int(node.get_clock().now().nanoseconds / 1000)
    pub.publish(msg)


def origin_already_set_dds(
    node: "Node",
    timeout_s: float,
    *,
    px4_namespace: str = "",
) -> bool:
    """True if PX4 reports a global origin (``VehicleLocalPosition.xy_global``)."""
    try:
        from px4_msgs.msg import VehicleLocalPosition
    except ImportError:
        return False
    from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

    ns = px4_namespace.rstrip("/")
    topic = f"{ns}/fmu/out/vehicle_local_position" if ns else "/fmu/out/vehicle_local_position"
    qos = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
    )
    got = {"ok": False}

    def _on_msg(msg: "VehicleLocalPosition") -> None:
        if bool(getattr(msg, "xy_global", False)):
            got["ok"] = True

    sub = node.create_subscription(VehicleLocalPosition, topic, _on_msg, qos)
    deadline = time.monotonic() + max(timeout_s, 0.0)
    while time.monotonic() < deadline and not got["ok"]:
        try:
            import rclpy

            rclpy.spin_once(node, timeout_sec=0.05)
        except Exception:
            time.sleep(0.05)
    node.destroy_subscription(sub)
    return bool(got["ok"])


def maybe_set_ekf_origin(
    node: "Node",
    *,
    backend: str,
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
    timeout_s: float,
    connection: Optional["MavlinkConnection"] = None,
    mavros_namespace: str = "mavros",
    px4_namespace: str = "",
) -> str:
    """
    Skip if origin already present; otherwise send once.

    Returns
    -------
    str
        ``"skipped"``, ``"sent"``, or ``"failed: …"``.
    """
    try:
        if backend == "mavlink":
            if connection is None:
                return "failed: no MAVLink connection"
            if origin_already_set_mavlink(connection, timeout_s):
                return "skipped"
            send_mavlink_origin(connection, lat_deg, lon_deg, alt_m)
            return "sent"
        if backend == "mavros":
            if origin_already_set_mavros(node, timeout_s, namespace=mavros_namespace):
                return "skipped"
            send_mavros_origin(node, lat_deg, lon_deg, alt_m, namespace=mavros_namespace)
            return "sent"
        if backend == "dds":
            if origin_already_set_dds(node, timeout_s, px4_namespace=px4_namespace):
                return "skipped"
            send_dds_origin(node, lat_deg, lon_deg, alt_m, px4_namespace=px4_namespace)
            return "sent"
        return f"failed: unknown backend {backend!r}"
    except Exception as exc:  # noqa: BLE001 — report to caller as status string
        return f"failed: {exc}"
