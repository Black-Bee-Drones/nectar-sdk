# With and without Nectar SDK

Same behaviors with Nectar’s public APIs and with complete scripts against the
underlying stacks. Expand each **Without Nectar** block for the full script.

| Area | Mission code stays | What changes |
|------|--------------------|--------------|
| [Control](#control) | `takeoff` / `move_to` / `land` | Factory key + config (transport, pose) |
| [Vision](#vision) | Frame access / handler callback | Camera `source` string (+ config) |
| [AI](#ai) | `detect` / `segment` / `classify` result shape | Model id + optional `framework` |
| [Composition](#composition) | Centering loop + PID | Transport, pose, camera, perception backend |

Module reference: [Control](nectar/nectar/control/README.md),
[Vision](nectar/nectar/vision/README.md),
[Cameras](nectar/nectar/vision/camera/README.md),
[AI](nectar/nectar/ai/README.md).
Composition builds a short mission from all three.

---

## [Control](nectar/nectar/control/README.md)

Takeoff, move, and land. Factory key and config select the transport; mission
calls stay the same.

### Position control

Takeoff to 2 m → move 5 m forward in the body frame → land. With Nectar only the
factory key and config change between transports.

!!! note "Navigation method"
    These pairs use `NavigationMethod.POSITION` (FCU holds the local setpoint) so
    the without scripts stay a fair counterpart. Field missions more often drive
    velocity with companion
    [`PIDController`](nectar/nectar/control/pid/README.md)
    (see [Composition](#composition)). The SDK default for `move_to` is `PID_EKF`
    — [Vehicle core](nectar/nectar/control/vehicle/README.md).

#### ArduPilot · MAVROS

!!! tip "Prerequisites"
    FCU reachable over MAVROS. With Nectar and `start_driver=False`, start the
    driver in another terminal: `make driver DRONE=mavros` (see
    [Drone drivers](docs/setup/drivers.md)). Without Nectar, run `mavros_node`
    (or the same `make driver`) yourself before the script.

```python
import nectar
from nectar.control import DroneFactory, MavrosConfig, NavigationMethod, PoseSource

nectar.init()
drone = DroneFactory.create(
    "mavros", MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
)
drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3, method=NavigationMethod.POSITION)
drone.land()
drone.cleanup()
nectar.shutdown()
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import math
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import PositionTarget, State
from mavros_msgs.srv import CommandBool, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

_POSITION_MASK = (
    PositionTarget.IGNORE_VX
    | PositionTarget.IGNORE_VY
    | PositionTarget.IGNORE_VZ
    | PositionTarget.IGNORE_AFX
    | PositionTarget.IGNORE_AFY
    | PositionTarget.IGNORE_AFZ
    | PositionTarget.IGNORE_YAW_RATE
)


def yaw_from_quat(q) -> float:
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class MavrosPilot(Node):
    def __init__(self) -> None:
        super().__init__("mavros_position_mission")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.state = State()
        self.pose = PoseStamped()
        self.create_subscription(State, "/mavros/state", lambda m: setattr(self, "state", m), 10)
        self.create_subscription(
            PoseStamped, "/mavros/local_position/pose", lambda m: setattr(self, "pose", m), qos
        )
        self.setpoint_pub = self.create_publisher(PositionTarget, "/mavros/setpoint_raw/local", 10)
        self.mode_cli = self.create_client(SetMode, "/mavros/set_mode")
        self.arm_cli = self.create_client(CommandBool, "/mavros/cmd/arming")
        self.takeoff_cli = self.create_client(CommandTOL, "/mavros/cmd/takeoff")
        self.land_cli = self.create_client(CommandTOL, "/mavros/cmd/land")

    def call(self, client, request, timeout: float = 5.0):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f"service unavailable: {client.srv_name}")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
        if future.result() is None:
            raise RuntimeError(f"service call failed: {client.srv_name}")
        return future.result()

    def wait_connected(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state.connected:
                return
        raise TimeoutError("FCU not connected via MAVROS")

    def set_guided_and_arm(self) -> None:
        req = SetMode.Request()
        req.custom_mode = "GUIDED"
        self.call(self.mode_cli, req)
        while self.state.mode != "GUIDED":
            rclpy.spin_once(self, timeout_sec=0.1)
        arm = CommandBool.Request()
        arm.value = True
        self.call(self.arm_cli, arm)
        while not self.state.armed:
            rclpy.spin_once(self, timeout_sec=0.1)

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        req = CommandTOL.Request()
        req.altitude = float(altitude)
        self.call(self.takeoff_cli, req)
        start_z = self.pose.pose.position.z
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.pose.pose.position.z >= start_z + altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def move_body(self, forward: float, left: float, up: float, precision: float = 0.3) -> None:
        rclpy.spin_once(self, timeout_sec=0.1)
        p = self.pose.pose.position
        yaw = yaw_from_quat(self.pose.pose.orientation)
        c, s = math.cos(yaw), math.sin(yaw)
        tx = p.x + forward * c - left * s
        ty = p.y + forward * s + left * c
        tz = p.z + up
        target = PositionTarget()
        target.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        target.type_mask = _POSITION_MASK
        target.position.x = float(tx)
        target.position.y = float(ty)
        target.position.z = float(tz)
        target.yaw = float(yaw)
        deadline = time.time() + 60.0
        while time.time() < deadline:
            target.header.stamp = self.get_clock().now().to_msg()
            self.setpoint_pub.publish(target)
            rclpy.spin_once(self, timeout_sec=0.05)
            dx = self.pose.pose.position.x - tx
            dy = self.pose.pose.position.y - ty
            dz = self.pose.pose.position.z - tz
            if math.sqrt(dx * dx + dy * dy + dz * dz) <= precision:
                return
        raise TimeoutError("position settle")

    def land(self) -> None:
        req = CommandTOL.Request()
        req.altitude = 0.0
        self.call(self.land_cli, req)


def main() -> None:
    rclpy.init()
    node = MavrosPilot()
    try:
        node.wait_connected()
        node.set_guided_and_arm()
        time.sleep(1.0)
        node.takeoff(2.0)
        node.move_body(forward=5.0, left=0.0, up=0.0, precision=0.3)
        node.land()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

</details>

#### ArduPilot · MAVLink

!!! tip "Prerequisites"
    FCU on a pymavlink URL (SITL or serial). With Nectar, set the URL in
    `MavlinkConfig` (defaults cover common SITL ports). Without Nectar, set the
    connection string in the script (`udp:…`, `tcp:127.0.0.1:5762`,
    `/dev/ttyUSB0`, …). No MAVROS process is required.

```python
import nectar
from nectar.control import DroneFactory, MavlinkConfig, NavigationMethod, PoseSource

nectar.init()
drone = DroneFactory.create(
    "mavlink", MavlinkConfig(pose_source=PoseSource.GPS, start_driver=False)
)
drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3, method=NavigationMethod.POSITION)
drone.land()
drone.cleanup()
nectar.shutdown()
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import math
import time

from pymavlink import mavutil

_M = mavutil.mavlink
_POSITION_MASK = (
    _M.POSITION_TARGET_TYPEMASK_VX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_VY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_VZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE
)


def enu_to_ned(x: float, y: float, z: float):
    return y, x, -z


def ned_to_enu(n: float, e: float, d: float):
    return e, n, -d


class MavlinkPilot:
    def __init__(self, connection_string: str = "udp:127.0.0.1:14550") -> None:
        self.master = mavutil.mavlink_connection(connection_string, autoreconnect=True)
        self.master.wait_heartbeat()
        self._local = None
        self._yaw_ned = 0.0
        self._request_streams()

    def _request_streams(self) -> None:
        for msg_id, hz in (
            (_M.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 20),
            (_M.MAVLINK_MSG_ID_ATTITUDE, 20),
            (_M.MAVLINK_MSG_ID_HEARTBEAT, 1),
        ):
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                _M.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                msg_id,
                int(1e6 / hz),
                0,
                0,
                0,
                0,
                0,
            )

    def _spin(self, timeout: float = 0.5):
        """Drain the link; LOCAL_POSITION_NED has no yaw — attitude carries it."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.master.recv_match(
                blocking=True, timeout=max(0.0, deadline - time.time())
            )
            if msg is None:
                break
            t = msg.get_type()
            if t == "LOCAL_POSITION_NED":
                self._local = msg
            elif t == "ATTITUDE":
                self._yaw_ned = float(msg.yaw)
        return self._local

    def set_mode(self, mode: str) -> None:
        mapping = self.master.mode_mapping()
        if mode not in mapping:
            raise RuntimeError(f"mode {mode!r} not in mode_mapping")
        self.master.mav.set_mode_send(
            self.master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mapping[mode],
        )
        deadline = time.time() + 5.0
        while time.time() < deadline:
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if hb and mavutil.mode_string_v10(hb) == mode:
                return
        raise TimeoutError(f"failed to enter {mode}")

    def arm(self) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        deadline = time.time() + 6.0
        while time.time() < deadline:
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if hb and (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                return
        raise TimeoutError("arm failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            float(altitude),
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._spin()
            if msg is not None and -msg.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def move_body(self, forward: float, left: float, up: float, precision: float = 0.3) -> None:
        msg = self._spin(timeout=2.0)
        if msg is None:
            raise RuntimeError("no LOCAL_POSITION_NED")
        x, y, z = ned_to_enu(msg.x, msg.y, msg.z)
        yaw_enu = math.pi / 2.0 - self._yaw_ned
        c, s = math.cos(yaw_enu), math.sin(yaw_enu)
        tx = x + forward * c - left * s
        ty = y + forward * s + left * c
        tz = z + up
        n, e, d = enu_to_ned(tx, ty, tz)
        yaw_ned = self._yaw_ned
        deadline = time.time() + 60.0
        while time.time() < deadline:
            self.master.mav.set_position_target_local_ned_send(
                0,
                self.master.target_system,
                self.master.target_component,
                _M.MAV_FRAME_LOCAL_NED,
                _POSITION_MASK,
                n,
                e,
                d,
                0,
                0,
                0,
                0,
                0,
                0,
                yaw_ned,
                0,
            )
            msg = self._spin(timeout=0.2)
            if msg is None:
                continue
            cx, cy, cz = ned_to_enu(msg.x, msg.y, msg.z)
            if math.sqrt((cx - tx) ** 2 + (cy - ty) ** 2 + (cz - tz) ** 2) <= precision:
                return
        raise TimeoutError("position settle")

    def land(self) -> None:
        self.set_mode("LAND")


def main() -> None:
    pilot = MavlinkPilot("udp:127.0.0.1:14550")
    pilot.set_mode("GUIDED")
    pilot.arm()
    time.sleep(1.0)
    pilot.takeoff(2.0)
    pilot.move_body(forward=5.0, left=0.0, up=0.0, precision=0.3)
    pilot.land()


if __name__ == "__main__":
    main()
```

</details>

#### PX4 · uXRCE-DDS

!!! tip "Prerequisites"
    PX4 with uXRCE-DDS client and `px4_msgs` in the workspace. With Nectar and
    `start_driver=False`, start the agent: `make driver-px4-dds`. Without Nectar,
    run MicroXRCEAgent (same command) before the script.

```python
import nectar
from nectar.control import DroneFactory, NavigationMethod, PoseSource, Px4DdsConfig

nectar.init()
drone = DroneFactory.create(
    "px4_dds", Px4DdsConfig(pose_source=PoseSource.GPS, start_driver=False)
)
drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3, method=NavigationMethod.POSITION)
drone.land()
drone.cleanup()
nectar.shutdown()
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import math
import time

import rclpy
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

_ARMING_STATE_ARMED = 2
_NAV_STATE_OFFBOARD = 14


def enu_to_ned(x: float, y: float, z: float):
    return y, x, -z


def yaw_enu_to_ned(yaw_enu: float) -> float:
    return math.pi / 2.0 - yaw_enu


class Px4DdsPilot(Node):
    def __init__(self) -> None:
        super().__init__("px4_dds_position_mission")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.local = None
        self.status = None
        self._sp_n = self._sp_e = self._sp_d = 0.0
        self._sp_yaw = 0.0
        self._position_mode = True
        self.create_subscription(
            VehicleLocalPosition, "/fmu/out/vehicle_local_position_v1", self._on_local, qos
        )
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status_v4", self._on_status, qos)
        self.offboard_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", 10)
        self.setpoint_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", 10)
        self.command_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", 10)
        self.create_timer(0.05, self._pump)

    def _now_us(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def _on_local(self, msg: VehicleLocalPosition) -> None:
        self.local = msg

    def _on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

    def _pump(self) -> None:
        mode = OffboardControlMode()
        mode.timestamp = self._now_us()
        mode.position = self._position_mode
        mode.velocity = not self._position_mode
        self.offboard_pub.publish(mode)
        sp = TrajectorySetpoint()
        sp.timestamp = self._now_us()
        if self._position_mode:
            sp.position = [self._sp_n, self._sp_e, self._sp_d]
            sp.velocity = [math.nan, math.nan, math.nan]
        else:
            sp.position = [math.nan, math.nan, math.nan]
            sp.velocity = [0.0, 0.0, 0.0]
        sp.yaw = self._sp_yaw
        sp.yawspeed = math.nan
        self.setpoint_pub.publish(sp)

    def _command(self, command: int, **params) -> None:
        msg = VehicleCommand()
        msg.timestamp = self._now_us()
        msg.command = int(command)
        for i in range(1, 8):
            setattr(msg, f"param{i}", float(params.get(f"param{i}", 0.0)))
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)

    def wait_telemetry(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.local is not None and self.status is not None:
                return
        raise TimeoutError("no PX4 telemetry on uXRCE-DDS")

    def hold_current(self) -> None:
        assert self.local is not None
        self._position_mode = True
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z)
        self._sp_yaw = yaw_enu_to_ned(math.pi / 2.0 - float(self.local.heading))

    def enter_offboard_and_arm(self) -> None:
        self.hold_current()
        for _ in range(20):
            rclpy.spin_once(self, timeout_sec=0.05)
        self._command(176, param1=1.0, param2=6.0, param3=0.0)
        self._command(400, param1=1.0)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if (
                self.status is not None
                and self.status.arming_state == _ARMING_STATE_ARMED
                and self.status.nav_state == _NAV_STATE_OFFBOARD
            ):
                return
        raise TimeoutError("OFFBOARD arm failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        assert self.local is not None
        self._position_mode = True
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z) - float(altitude)
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.local is not None and -self.local.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def move_body(self, forward: float, left: float, up: float, precision: float = 0.3) -> None:
        assert self.local is not None
        ex0 = float(self.local.y)
        ey0 = float(self.local.x)
        ez0 = -float(self.local.z)
        yaw_enu = math.pi / 2.0 - float(self.local.heading)
        c, s = math.cos(yaw_enu), math.sin(yaw_enu)
        ex = ex0 + forward * c - left * s
        ey = ey0 + forward * s + left * c
        ez = ez0 + up
        tn, te, td = enu_to_ned(ex, ey, ez)
        self._sp_n, self._sp_e, self._sp_d = tn, te, td
        self._sp_yaw = yaw_enu_to_ned(yaw_enu)
        deadline = time.time() + 60.0
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.local is None:
                continue
            cx, cy, cz = float(self.local.y), float(self.local.x), -float(self.local.z)
            if math.sqrt((cx - ex) ** 2 + (cy - ey) ** 2 + (cz - ez) ** 2) <= precision:
                return
        raise TimeoutError("position settle")

    def land(self) -> None:
        self._command(176, param1=1.0, param2=4.0, param3=6.0)


def main() -> None:
    rclpy.init()
    node = Px4DdsPilot()
    try:
        node.wait_telemetry()
        node.enter_offboard_and_arm()
        node.takeoff(2.0)
        node.move_body(forward=5.0, left=0.0, up=0.0, precision=0.3)
        node.land()
        time.sleep(2.0)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

</details>

### Pose source

GPS (outdoor) vs external vision pose (indoor). Mission calls stay the same;
change `pose_source`, the factory key, and — when needed — the pose topic.
Any publisher that outputs the expected pose message works (Isaac ROS VSLAM,
T265, Gazebo ground truth, …); the SDK path delivers it to the FCU as external
navigation. Wiring details:
[Localization](nectar/nectar/control/localization/README.md).

!!! tip "Prerequisites"
    Indoor: a pose producer on the configured topic, plus the transport’s vision
    path (`make driver … ENV=indoor`, or `vision_pose.launch.py` for
    mavros/mavlink/dds). FCU EKF must accept external nav either way.

```python
import nectar
from nectar.control import (
    DroneFactory,
    MavlinkConfig,
    MavrosConfig,
    PoseSource,
    Px4DdsConfig,
)

nectar.init()
# Same takeoff / move / land after create. Pick one:
drone = DroneFactory.create(
    "mavros",
    MavrosConfig(pose_source=PoseSource.VISION, start_driver=False),
)
# drone = DroneFactory.create(
#     "mavlink",
#     MavlinkConfig(
#         pose_source=PoseSource.VISION,
#         vision_pose_topic="/visual_slam/tracking/vo_pose_covariance",  # any pose topic
#         start_driver=False,
#     ),
# )
# drone = DroneFactory.create(
#     "px4_dds", Px4DdsConfig(pose_source=PoseSource.VISION, start_driver=False)
# )
drone.takeoff(altitude=2.0)
drone.land()
drone.cleanup()
nectar.shutdown()
```

<details markdown>
<summary>Without Nectar (MAVROS relay example)</summary>

```python
#!/usr/bin/env python3
"""Relay an external pose topic into MAVROS vision_pose (FCU EKF).

Topic names are parameters — match your producer. MAVLink without Nectar sends
VISION_POSITION_ESTIMATE instead; PX4 DDS publishes VehicleOdometry. See
Localization README for those paths.
"""
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data


class VisionPoseRelay(Node):
    def __init__(
        self,
        input_topic: str = "/visual_slam/tracking/vo_pose_covariance",
        output_topic: str = "/mavros/vision_pose/pose_cov",
    ) -> None:
        super().__init__("vision_pose_relay")
        self.pub = self.create_publisher(
            PoseWithCovarianceStamped, output_topic, qos_profile_sensor_data
        )
        self.create_subscription(
            PoseWithCovarianceStamped, input_topic, self._on_pose, qos_profile_sensor_data
        )

    def _on_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = VisionPoseRelay()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

</details>

---

## [Vision](nectar/nectar/vision/README.md)

`CameraFactory` / `ImageHandler` open any supported camera; algorithms and
learning run on the frames. Drivers:
[Cameras](nectar/nectar/vision/camera/README.md).

A single USB open is already short without Nectar. The comparison matters when
the same handler/callback must move across backends —
[Change camera source](#change-camera-source), [ROS image topic](#ros-image-topic),
[Depth · RealSense](#depth--realsense).

### Webcam

!!! tip "Prerequisites"
    USB webcam visible to OpenCV (`/dev/video*`). No extra Nectar driver.

```python
from nectar.vision.camera import CameraFactory

cam = CameraFactory.from_source("webcam")
cam.start()
frame = cam.get_frame()
cam.close()
if frame is None:
    raise RuntimeError("failed to read frame")
print(frame.shape)
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import cv2


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("cannot open webcam")
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("failed to read frame")
    print(frame.shape)


if __name__ == "__main__":
    main()
```

</details>

### ROS image topic

!!! tip "Prerequisites"
    A node publishing `sensor_msgs/Image` on the topic (camera driver or
    simulator). Call `nectar.init()` so the subscription shares the SDK runtime.
    Use `ROSConfig(compressed=True)` / `CompressedImage` if the topic is
    compressed.

```python
import nectar
from nectar.vision.camera import CameraFactory

nectar.init()
cam = CameraFactory.from_source("/camera/color/image_raw")
cam.start()
frame = cam.get_frame(wait_for_new=True, timeout=2.0)
cam.close()
nectar.shutdown()
if frame is None:
    raise RuntimeError("failed to read frame")
print(frame.shape)
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


class OneShotCam(Node):
    def __init__(self, topic: str = "/camera/color/image_raw") -> None:
        super().__init__("oneshot_cam")
        self.bridge = CvBridge()
        self.frame = None
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(Image, topic, self._on_image, qos)

    def _on_image(self, msg: Image) -> None:
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")


def main() -> None:
    rclpy.init()
    node = OneShotCam()
    try:
        while node.frame is None:
            rclpy.spin_once(node, timeout_sec=0.1)
        print(node.frame.shape)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

</details>

### Depth · RealSense

Color frame plus a depth sample at the image center. Same pattern applies to
other depth backends (`oakd`, `ros_depth`) via the factory key and config.

!!! tip "Prerequisites"
    Intel RealSense D4xx attached. Without Nectar also needs `pyrealsense2`.
    See [Cameras](nectar/nectar/vision/camera/README.md) for RealSense / OAK
    setup.

```python
from nectar.vision.camera import CameraFactory

cam = CameraFactory.from_source("realsense")
cam.start()
frame = cam.get_frame()
if frame is None:
    raise RuntimeError("no color frame")
h, w = frame.shape[:2]
distance_m = cam.get_distance(w // 2, h // 2)
depth = cam.get_depth_frame()
cam.close()
print(frame.shape, None if depth is None else depth.shape, distance_m)
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import numpy as np
import pyrealsense2 as rs


def main() -> None:
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    profile = pipeline.start(config)
    align = rs.align(rs.stream.color)
    try:
        frames = pipeline.wait_for_frames(timeout_ms=5000)
        frames = align.process(frames)
        color = np.asanyarray(frames.get_color_frame().get_data())
        depth_frame = frames.get_depth_frame()
        depth = np.asanyarray(depth_frame.get_data())
        h, w = color.shape[:2]
        distance_m = depth_frame.get_distance(w // 2, h // 2)
        print(color.shape, depth.shape, distance_m)
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
```

</details>

### ArUco pose

One frame → marker id and camera-frame translation. Same
[`Aruco`](nectar/nectar/vision/algorithms/README.md) call whether the frame came
from a webcam, ROS topic, or depth camera (see [Change camera source](#change-camera-source)).
Full flight loop: [ArUco center](#aruco-center).

!!! tip "Prerequisites"
    USB webcam. Calibration on disk: Nectar loads
    `camera_matrix.txt` / `camera_distortion.txt` via
    [`CameraCalibration`](nectar/nectar/vision/camera/README.md)
    (package default directory unless you pass another). Without Nectar, load the
    same intrinsics yourself (`camera_matrix.npy` / `dist_coeffs.npy` below, or
    equivalent). Marker dictionary and physical `tag_size` must match the printed
    tag.

```python
from nectar.vision import Aruco
from nectar.vision.camera import CameraFactory

cam = CameraFactory.from_source("webcam")
cam.start()
frame = cam.get_frame()
cam.close()
if frame is None:
    raise RuntimeError("failed to read frame")

aruco = Aruco(marker_dict=5, tag_size=0.2)
marker_id, tvec, yaw = aruco.pose_estimate(frame)
print(marker_id, None if tvec is None else tvec.tolist(), yaw)
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import cv2
import cv2.aruco as aruco
import numpy as np

TAG_SIZE = 0.2


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("cannot open webcam")
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("failed to read frame")

    camera_matrix = np.load("camera_matrix.npy")
    dist_coeffs = np.load("dist_coeffs.npy")
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_1000)
    detector = aruco.ArucoDetector(dictionary, aruco.DetectorParameters())
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        print(None, None, None)
        return
    rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
        corners, TAG_SIZE, camera_matrix, dist_coeffs
    )
    tvec = tvecs[0][0]
    # Yaw from top edge of the first marker (same idea as Nectar's helper).
    tl, tr = corners[0][0][0], corners[0][0][1]
    yaw = float(np.degrees(np.arctan2(tr[1] - tl[1], tr[0] - tl[0]))) % 360.0
    print(int(ids[0][0]), tvec.tolist(), yaw)


if __name__ == "__main__":
    main()
```

</details>

### Change camera source

Same callback and handler; only the `source` string (and optional config) changes.
Other registered keys: `oakd`, `t265`, `c920`, `imx219`, `file`, `ros_depth` —
[Cameras](nectar/nectar/vision/camera/README.md).
`ImageHandler.run()` + `nectar.spin()` is the streaming form; the one-shot
`CameraFactory` / `take_photo` pattern appears in the sections above and in
[Composition](#composition).

!!! tip "Prerequisites"
    Match the chosen `source` (webcam, ROS topic, RealSense, …). With Nectar the
    mission code does not change; only the string/config does. Without Nectar each
    backend keeps its own open path (see the without scripts above).

```python
import nectar
from nectar.vision.camera import ImageHandler

nectar.init()

def on_frame(frame) -> None:
    if frame is not None:
        print(frame.shape)

source = "webcam"  # or "/camera/color/image_raw", "realsense", "oakd", ...
ImageHandler(source, image_processing_callback=on_frame).run()
nectar.spin()
nectar.shutdown()
```

---

## [AI](nectar/nectar/ai/README.md)

[`Detector`](nectar/nectar/ai/detection/README.md),
[`Segmentor`](nectar/nectar/ai/segmentation/README.md), and
[`Classifier`](nectar/nectar/ai/classification/README.md). Model string and
optional `framework` select the backend; the task call and result fields stay
the same.

A single Ultralytics YOLO detect is already short without Nectar. The comparison
matters when you change framework or task without rewriting result parsing —
[Framework swap](#framework-swap), [Task flip](#task-flip).

### YOLO

!!! tip "Prerequisites"
    `ultralytics` installed; a readable image file (default `image.jpg` below).
    Weights download on first load.

```python
from nectar.ai.detection import Detector

detector = Detector("yolov8n.pt")
detector.load()
result = detector.detect("image.jpg")
for det in result:
    print(f"{det.class_name}: {det.confidence:.2f}")
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import sys

import cv2
from ultralytics import YOLO


def main(image_path: str) -> None:
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"cannot read {image_path}")
    model = YOLO("yolov8n.pt")
    out = model.predict(image, conf=0.25, verbose=False)[0]
    names = out.names
    for box in out.boxes:
        cls_id = int(box.cls.item())
        conf = float(box.conf.item())
        print(f"{names[cls_id]}: {conf:.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
```

</details>

### Framework swap

!!! tip "Prerequisites"
    Same image file for every model. Install the framework under test
    (`ultralytics`, `transformers` + `torch`, or `rfdetr`). Hub models may need
    network access.

```python
from nectar.ai.core import Framework
from nectar.ai.detection import Detector

image_path = "image.jpg"
for model, framework in (
    ("yolov8n.pt", None),
    ("rfdetr-medium", None),
    ("facebook/detr-resnet-50", Framework.TRANSFORMERS),
):
    detector = Detector(model, framework=framework)
    detector.load()
    for det in detector.detect(image_path):
        print(model, det.class_name, det.confidence)
```

<details markdown>
<summary>Without Nectar (Hugging Face DETR)</summary>

```python
#!/usr/bin/env python3
import sys

import cv2
import torch
from PIL import Image as PILImage
from transformers import AutoImageProcessor, AutoModelForObjectDetection


def main(image_path: str) -> None:
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise RuntimeError(f"cannot read {image_path}")
    pil = PILImage.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    processor = AutoImageProcessor.from_pretrained("facebook/detr-resnet-50")
    model = AutoModelForObjectDetection.from_pretrained("facebook/detr-resnet-50")
    model.eval()
    inputs = processor(images=pil, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    results = processor.post_process_object_detection(
        outputs, threshold=0.25, target_sizes=torch.tensor([pil.size[::-1]])
    )[0]
    id2label = model.config.id2label
    for score, label in zip(results["scores"], results["labels"]):
        print(f"{id2label[label.item()]}: {score.item():.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
```

</details>

<details markdown>
<summary>Without Nectar (RF-DETR)</summary>

```python
#!/usr/bin/env python3
import sys

import cv2
from PIL import Image as PILImage
from rfdetr import RFDETRMedium


def main(image_path: str) -> None:
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise RuntimeError(f"cannot read {image_path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    model = RFDETRMedium()
    detections = model.predict(PILImage.fromarray(rgb), threshold=0.25)
    for i in range(len(detections)):
        cls_id = int(detections.class_id[i])
        conf = float(detections.confidence[i])
        # Raw API returns class_id; map to names yourself (Nectar: det.class_name).
        print(f"{cls_id}: {conf:.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
```

</details>

### Task flip

Same image; switch among detection, segmentation, and classification entry points.

!!! tip "Prerequisites"
    `ultralytics` with detect, segment, and classification weights
    (`yolov8n.pt`, `yolov8n-seg.pt`, `yolov8n-cls.pt`). Image file
    `image.jpg` below (same as the without scripts).

```python
from nectar.ai.detection import Detector
from nectar.ai.segmentation import Segmentor
from nectar.ai.classification import Classifier

image_path = "image.jpg"

detector = Detector("yolov8n.pt")
detector.load()
for det in detector.detect(image_path):
    print(det.class_name, det.confidence)

segmentor = Segmentor("yolov8n-seg.pt")
segmentor.load()
for seg in segmentor.segment(image_path):
    print(seg.class_name, seg.confidence, seg.mask_area)

classifier = Classifier("yolov8n-cls.pt")
classifier.load()
cls = classifier.classify(image_path)
print(cls.top1_name, cls.top1_confidence)
```

<details markdown>
<summary>Without Nectar (YOLO segment)</summary>

```python
#!/usr/bin/env python3
import sys

import cv2
import numpy as np
from ultralytics import YOLO


def main(image_path: str) -> None:
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"cannot read {image_path}")
    model = YOLO("yolov8n-seg.pt")
    out = model.predict(image, conf=0.25, verbose=False)[0]
    names = out.names
    if out.masks is None:
        return
    for i, box in enumerate(out.boxes):
        cls_id = int(box.cls.item())
        conf = float(box.conf.item())
        mask = out.masks.data[i].cpu().numpy()
        area = int(np.count_nonzero(mask > 0.5))
        print(f"{names[cls_id]}: {conf:.2f}, mask_area={area}px")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
```

</details>

<details markdown>
<summary>Without Nectar (YOLO classify)</summary>

```python
#!/usr/bin/env python3
import sys

import cv2
from ultralytics import YOLO


def main(image_path: str) -> None:
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"cannot read {image_path}")
    model = YOLO("yolov8n-cls.pt")
    out = model.predict(image, verbose=False)[0]
    names = out.names
    top1 = int(out.probs.top1)
    conf = float(out.probs.top1conf)
    print(f"{names[top1]}: {conf:.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
```

</details>

---

## Composition

Short missions that combine control, vision, and (when needed) learning. The
centering loop is the same on both pairs; only factory key, pose config, and
camera source change to match the stack.

| Pair | Firmware / transport | Pose | Camera | Perception |
|------|----------------------|------|--------|------------|
| [Detect and center](#detect-and-center) | ArduPilot · MAVLink | Vision | Webcam | `Detector` |
| [ArUco center](#aruco-center) | PX4 · uXRCE-DDS | GPS | ROS image topic | `Aruco` |

### Detect and center

[`ImageHandler`](nectar/nectar/vision/camera/README.md) +
[`Detector`](nectar/nectar/ai/detection/README.md) +
[`PIDController`](nectar/nectar/control/pid/README.md) → body velocity until the
target is centered (ArduPilot · MAVLink, vision pose, webcam).

!!! tip "Prerequisites"
    FCU on a pymavlink URL; VSLAM/VIO publishing the vision pose topic (Nectar
    forwards it as `VISION_POSITION_ESTIMATE` when `pose_source=VISION` —
    [Pose source](#pose-source),
    [Localization](nectar/nectar/control/localization/README.md)); USB webcam;
    `ultralytics` for the without script. Gains and thresholds are
    mission-specific.

```python
import nectar
from nectar.ai.detection import Detector
from nectar.control import DroneFactory, MavlinkConfig, PIDController, PoseSource
from nectar.vision.camera import ImageHandler

CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_CLASS = "person"  # class name in the loaded model

nectar.init()
drone = DroneFactory.create(
    "mavlink", MavlinkConfig(pose_source=PoseSource.VISION, start_driver=False)
)
drone.takeoff(altitude=1.2)

detector = Detector("yolov8n.pt")
detector.load()

handler = ImageHandler(
    "webcam",
    image_processing_callback=lambda frame: detector.detect(frame),
)
handler.open()

pid_x = PIDController(kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4))
pid_y = PIDController(kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4))
pid_x.reset()
pid_y.reset()

lost = 0
while True:
    result = handler.take_photo()
    targets = result.filter_by_class([TARGET_CLASS]) if result else None
    if not targets:
        lost += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=1.0 / 30.0)
        if lost >= LOST_LIMIT:
            break
        continue
    lost = 0
    det = max(targets, key=lambda d: d.confidence)
    h, w = handler.img.shape[:2]
    cx, cy = det.center
    err_x = float(cx - w / 2.0)
    err_y = float(cy - h / 2.0)
    if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
        break
    # Downward camera: image x → body vy, image y → body vx (signs are mission-tuned).
    drone.move_velocity(
        vx=pid_y.update(err_y),
        vy=pid_x.update(-err_x),
        vz=0.0,
        duration=1.0 / 30.0,
    )

drone.land()
handler.cleanup()
drone.cleanup()
nectar.shutdown()
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import time

import cv2
from pymavlink import mavutil
from ultralytics import YOLO

CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_CLASS = "person"
_M = mavutil.mavlink
_VELOCITY_MASK = (
    _M.POSITION_TARGET_TYPEMASK_X_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_Y_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_Z_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_YAW_IGNORE
)


class PID:
    def __init__(self, kp: float, ki: float, kd: float, limits=(-0.4, 0.4)) -> None:
        self.kp, self.ki, self.kd = kp, ki, kd
        self.lo, self.hi = limits
        self.setpoint = 0.0
        self._i = 0.0
        self._prev_err = 0.0
        self._prev_t = None

    def reset(self) -> None:
        self._i = 0.0
        self._prev_err = 0.0
        self._prev_t = None

    def update(self, value: float) -> float:
        now = time.monotonic()
        err = self.setpoint - value
        if self._prev_t is None:
            self._prev_t = now
            self._prev_err = err
            return 0.0
        dt = max(now - self._prev_t, 1e-3)
        self._i = max(self.lo, min(self.hi, self._i + err * dt))
        d = (err - self._prev_err) / dt
        self._prev_err, self._prev_t = err, now
        out = self.kp * err + self.ki * self._i + self.kd * d
        return max(self.lo, min(self.hi, out))


class DetectCenter:
    """ArduPilot GUIDED over pymavlink + YOLO + webcam.

    Indoor EKF still needs an external VISION_POSITION_ESTIMATE feed (separate
    VSLAM relay). Nectar starts that bridge when pose_source=VISION.
    """

    def __init__(self, connection_string: str = "udp:127.0.0.1:14550") -> None:
        self.master = mavutil.mavlink_connection(connection_string, autoreconnect=True)
        self.master.wait_heartbeat()
        self._local = None
        self._request_streams()
        self.model = YOLO("yolov8n.pt")
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("cannot open webcam")
        self.pid_x = PID(kp=-0.002, ki=0.0, kd=0.0)
        self.pid_y = PID(kp=-0.002, ki=0.0, kd=0.0)

    def _request_streams(self) -> None:
        for msg_id, hz in (
            (_M.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 20),
            (_M.MAVLINK_MSG_ID_ATTITUDE, 20),
            (_M.MAVLINK_MSG_ID_HEARTBEAT, 1),
        ):
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                _M.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                msg_id,
                int(1e6 / hz),
                0,
                0,
                0,
                0,
                0,
            )

    def _spin_local(self, timeout: float = 0.5):
        msg = self.master.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=timeout)
        if msg is not None:
            self._local = msg
        return self._local

    def set_mode(self, mode: str) -> None:
        mapping = self.master.mode_mapping()
        if mode not in mapping:
            raise RuntimeError(f"mode {mode!r} not in mode_mapping")
        self.master.mav.set_mode_send(
            self.master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mapping[mode],
        )
        deadline = time.time() + 5.0
        while time.time() < deadline:
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if hb and mavutil.mode_string_v10(hb) == mode:
                return
        raise TimeoutError(f"failed to enter {mode}")

    def arm(self) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        deadline = time.time() + 6.0
        while time.time() < deadline:
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if hb and (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                return
        raise TimeoutError("arm failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            float(altitude),
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._spin_local()
            if msg is not None and -msg.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def publish_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        # Body FLU → MAV_FRAME_BODY_NED FRD
        vn, ve, vd = float(vx), -float(vy), -float(vz)
        self.master.mav.set_position_target_local_ned_send(
            0,
            self.master.target_system,
            self.master.target_component,
            _M.MAV_FRAME_BODY_NED,
            _VELOCITY_MASK,
            0.0,
            0.0,
            0.0,
            vn,
            ve,
            vd,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    def land(self) -> None:
        self.set_mode("LAND")

    def run_center(self) -> None:
        self.pid_x.reset()
        self.pid_y.reset()
        lost = 0
        rate = 1.0 / 30.0
        while True:
            ok, frame = self.cap.read()
            self._spin_local(timeout=0.0)
            if not ok or frame is None:
                continue
            out = self.model.predict(frame, conf=0.25, verbose=False)[0]
            names = out.names
            candidates = []
            if out.boxes is not None:
                for box in out.boxes:
                    cls_id = int(box.cls.item())
                    if names[cls_id] == TARGET_CLASS:
                        candidates.append(box)
            if not candidates:
                lost += 1
                self.publish_velocity(0.0, 0.0)
                time.sleep(rate)
                if lost >= LOST_LIMIT:
                    return
                continue
            lost = 0
            box = max(candidates, key=lambda b: float(b.conf.item()))
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            h, w = frame.shape[:2]
            err_x = float(cx - w / 2.0)
            err_y = float(cy - h / 2.0)
            if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
                self.publish_velocity(0.0, 0.0)
                return
            self.publish_velocity(self.pid_y.update(err_y), self.pid_x.update(-err_x))
            time.sleep(rate)

    def close(self) -> None:
        self.cap.release()


def main() -> None:
    pilot = DetectCenter("udp:127.0.0.1:14550")
    try:
        pilot.set_mode("GUIDED")
        pilot.arm()
        time.sleep(1.0)
        pilot.takeoff(1.2)
        pilot.run_center()
        pilot.land()
    finally:
        pilot.close()


if __name__ == "__main__":
    main()
```

</details>

!!! note "Vision pose without Nectar"
    Without Nectar you also maintain the VSLAM → `VISION_POSITION_ESTIMATE` relay
    yourself ([Pose source](#pose-source)).

### ArUco center

Same centering loop with
[`Aruco`](nectar/nectar/vision/algorithms/README.md) instead of a learning model
(PX4 · uXRCE-DDS, GPS pose, ROS image topic).

!!! tip "Prerequisites"
    PX4 with uXRCE-DDS client and `px4_msgs`; with Nectar run
    `make driver-px4-dds` when `start_driver=False`. A node publishing
    `sensor_msgs/Image` on the topic. Both sides need camera intrinsics and a
    matching marker: Nectar loads `camera_matrix.txt` /
    `camera_distortion.txt` via `CameraCalibration` when constructing
    `Aruco`; the without script loads `camera_matrix.npy` /
    `dist_coeffs.npy`. Dictionary `DICT_5X5_1000` and `tag_size` must match the
    printed tag.

```python
import nectar
from nectar.control import DroneFactory, PIDController, PoseSource, Px4DdsConfig
from nectar.vision import Aruco
from nectar.vision.camera import ImageHandler

CENTER_XY = 0.05
LOST_LIMIT = 30

nectar.init()
drone = DroneFactory.create(
    "px4_dds", Px4DdsConfig(pose_source=PoseSource.GPS, start_driver=False)
)
drone.takeoff(altitude=1.2)

aruco = Aruco(marker_dict=5, tag_size=0.2)
handler = ImageHandler(
    "/camera/color/image_raw",
    image_processing_callback=lambda frame: aruco.pose_estimate(frame),
)
handler.open()

pid_x = PIDController(kp=-0.4, ki=-0.02, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4))
pid_y = PIDController(kp=-0.4, ki=-0.02, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4))
pid_x.reset()
pid_y.reset()

lost = 0
while True:
    out = handler.take_photo()
    if out is None:
        continue
    marker_id, tvec, _yaw = out
    if marker_id is None or tvec is None:
        lost += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=1.0 / 30.0)
        if lost >= LOST_LIMIT:
            break
        continue
    lost = 0
    err_x, err_y = float(tvec[0]), float(tvec[1])
    if err_x * err_x + err_y * err_y <= CENTER_XY * CENTER_XY:
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
        break
    drone.move_velocity(
        vx=pid_x.update(err_x),
        vy=pid_y.update(err_y),
        vz=0.0,
        duration=1.0 / 30.0,
    )

drone.land()
handler.cleanup()
drone.cleanup()
nectar.shutdown()
```

<details markdown>
<summary>Without Nectar</summary>

```python
#!/usr/bin/env python3
import math
import time

import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from cv_bridge import CvBridge
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

CENTER_XY = 0.05
LOST_LIMIT = 30
TAG_SIZE = 0.2
_ARMING_STATE_ARMED = 2
_NAV_STATE_OFFBOARD = 14


class PID:
    def __init__(self, kp: float, ki: float, kd: float, limits=(-0.4, 0.4)) -> None:
        self.kp, self.ki, self.kd = kp, ki, kd
        self.lo, self.hi = limits
        self.setpoint = 0.0
        self._i = 0.0
        self._prev_err = 0.0
        self._prev_t = None

    def reset(self) -> None:
        self._i = 0.0
        self._prev_err = 0.0
        self._prev_t = None

    def update(self, value: float) -> float:
        now = time.monotonic()
        err = self.setpoint - value
        if self._prev_t is None:
            self._prev_t = now
            self._prev_err = err
            return 0.0
        dt = max(now - self._prev_t, 1e-3)
        self._i = max(self.lo, min(self.hi, self._i + err * dt))
        d = (err - self._prev_err) / dt
        self._prev_err, self._prev_t = err, now
        out = self.kp * err + self.ki * self._i + self.kd * d
        return max(self.lo, min(self.hi, out))


def enu_to_ned(x: float, y: float, z: float):
    return y, x, -z


def yaw_enu_to_ned(yaw_enu: float) -> float:
    return math.pi / 2.0 - yaw_enu


class ArucoCenter(Node):
    """PX4 OFFBOARD over uXRCE-DDS + ArUco + ROS Image topic (GPS local pose)."""

    def __init__(self, image_topic: str = "/camera/color/image_raw") -> None:
        super().__init__("aruco_center_px4")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.local = None
        self.status = None
        self.frame = None
        self.bridge = CvBridge()
        self._sp_n = self._sp_e = self._sp_d = 0.0
        self._sp_yaw = 0.0
        self._vn = self._ve = self._vd = 0.0
        self._velocity_mode = False

        self.create_subscription(
            VehicleLocalPosition, "/fmu/out/vehicle_local_position_v1", self._on_local, qos
        )
        self.create_subscription(VehicleStatus, "/fmu/out/vehicle_status_v4", self._on_status, qos)
        self.create_subscription(Image, image_topic, self._on_image, qos)
        self.offboard_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", 10)
        self.setpoint_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", 10)
        self.command_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", 10)
        self.create_timer(0.05, self._pump)

        self.dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_1000)
        self.detector = aruco.ArucoDetector(self.dictionary, aruco.DetectorParameters())
        self.camera_matrix = np.load("camera_matrix.npy")
        self.dist_coeffs = np.load("dist_coeffs.npy")
        self.pid_x = PID(kp=-0.4, ki=-0.02, kd=0.0)
        self.pid_y = PID(kp=-0.4, ki=-0.02, kd=0.0)

    def _now_us(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def _on_local(self, msg: VehicleLocalPosition) -> None:
        self.local = msg

    def _on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

    def _on_image(self, msg: Image) -> None:
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def _pump(self) -> None:
        mode = OffboardControlMode()
        mode.timestamp = self._now_us()
        mode.position = not self._velocity_mode
        mode.velocity = self._velocity_mode
        self.offboard_pub.publish(mode)
        sp = TrajectorySetpoint()
        sp.timestamp = self._now_us()
        if self._velocity_mode:
            sp.position = [math.nan, math.nan, math.nan]
            sp.velocity = [self._vn, self._ve, self._vd]
            sp.yaw = math.nan
        else:
            sp.position = [self._sp_n, self._sp_e, self._sp_d]
            sp.velocity = [math.nan, math.nan, math.nan]
            sp.yaw = self._sp_yaw
        sp.yawspeed = math.nan
        self.setpoint_pub.publish(sp)

    def _command(self, command: int, **params) -> None:
        msg = VehicleCommand()
        msg.timestamp = self._now_us()
        msg.command = int(command)
        for i in range(1, 8):
            setattr(msg, f"param{i}", float(params.get(f"param{i}", 0.0)))
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)

    def wait_telemetry(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.local is not None and self.status is not None:
                return
        raise TimeoutError("no PX4 telemetry on uXRCE-DDS")

    def hold_current(self) -> None:
        assert self.local is not None
        self._velocity_mode = False
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z)
        self._sp_yaw = yaw_enu_to_ned(math.pi / 2.0 - float(self.local.heading))

    def enter_offboard_and_arm(self) -> None:
        self.hold_current()
        for _ in range(20):
            rclpy.spin_once(self, timeout_sec=0.05)
        self._command(176, param1=1.0, param2=6.0, param3=0.0)
        self._command(400, param1=1.0)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if (
                self.status is not None
                and self.status.arming_state == _ARMING_STATE_ARMED
                and self.status.nav_state == _NAV_STATE_OFFBOARD
            ):
                return
        raise TimeoutError("OFFBOARD arm failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        assert self.local is not None
        self._velocity_mode = False
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z) - float(altitude)
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.local is not None and -self.local.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def publish_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        # Body FLU → world ENU using PX4 heading, then ENU → NED for TrajectorySetpoint.
        assert self.local is not None
        yaw_enu = math.pi / 2.0 - float(self.local.heading)
        c, s = math.cos(yaw_enu), math.sin(yaw_enu)
        ve = vx * c - vy * s
        vn = vx * s + vy * c
        self._vn, self._ve, self._vd = enu_to_ned(ve, vn, vz)
        self._velocity_mode = True

    def land(self) -> None:
        self._command(176, param1=1.0, param2=4.0, param3=6.0)

    def estimate_pose(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        if ids is None:
            return None, None
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, TAG_SIZE, self.camera_matrix, self.dist_coeffs
        )
        return int(ids[0][0]), tvecs[0][0]

    def run_center(self) -> None:
        self.pid_x.reset()
        self.pid_y.reset()
        lost = 0
        rate = 1.0 / 30.0
        while True:
            now = time.time()
            rclpy.spin_once(self, timeout_sec=0.0)
            frame = self.frame
            if frame is None:
                continue
            marker_id, tvec = self.estimate_pose(frame)
            if tvec is None:
                lost += 1
                self.publish_velocity(0.0, 0.0)
                while time.time() - now < rate:
                    rclpy.spin_once(self, timeout_sec=0.01)
                if lost >= LOST_LIMIT:
                    return
                continue
            lost = 0
            err_x, err_y = float(tvec[0]), float(tvec[1])
            if err_x * err_x + err_y * err_y <= CENTER_XY * CENTER_XY:
                self.publish_velocity(0.0, 0.0)
                return
            self.publish_velocity(self.pid_x.update(err_x), self.pid_y.update(err_y))
            while time.time() - now < rate:
                rclpy.spin_once(self, timeout_sec=0.01)


def main() -> None:
    rclpy.init()
    node = ArucoCenter()
    try:
        node.wait_telemetry()
        node.enter_offboard_and_arm()
        node.takeoff(1.2)
        node.run_center()
        node.land()
        time.sleep(2.0)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

</details>

!!! note "What changes"
    Without Nectar the stacks diverge (pymavlink + OpenCV capture vs PX4 DDS
    offboard + ROS image subscriber). With Nectar the differences are the factory
    key, config, and `ImageHandler` source string.
