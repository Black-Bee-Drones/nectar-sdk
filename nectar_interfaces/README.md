# Nectar Interfaces

Custom ROS2 message definitions for the Nectar SDK.

## Overview

This package provides custom ROS2 message types used by vision and control modules to publish detection results and sensor data.

## Messages

### ArucoTransforms

ArUco marker pose estimation data.

**File:** `msg/ArucoTransforms.msg`

```
int32 id
geometry_msgs/Vector3 translation
std_msgs/Float64 yaw
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int32` | Detected marker ID |
| `translation` | `geometry_msgs/Vector3` | 3D position relative to camera (meters) |
| `yaw` | `std_msgs/Float64` | Marker rotation angle (degrees, 0-360) |

**Published by:** `ArucoNode` · **Topic:** `/aruco/pose_estimate`

---

### LineInfo

Line detection state information.

**File:** `msg/LineInfo.msg`

```
float64 center_x
float64 center_y
float64 angle
float64 width
float64 height
```

| Field | Type | Description |
|-------|------|-------------|
| `center_x` | `float64` | Line center X coordinate (pixels) |
| `center_y` | `float64` | Line center Y coordinate (pixels) |
| `angle` | `float64` | Line angle (degrees, -90 to +90) |
| `width` | `float64` | Average line width (pixels) |
| `height` | `float64` | Average line height (pixels) |

**Published by:** `LineDetectionNode` · **Topic:** `line_state/{color}` (e.g. `line_state/blue`)

---

### PhotoInfo

Photo metadata with coordinates.

**File:** `msg/PhotoInfo.msg`

```
float64[] coordinates
string photo_num
```

| Field | Type | Description |
|-------|------|-------------|
| `coordinates` | `float64[]` | Array of coordinate values |
| `photo_num` | `string` | Photo identifier/number |

---

## Dependencies

| Package | Description |
|---------|-------------|
| `geometry_msgs` | Standard ROS2 geometry message types (Vector3) |
| `std_msgs` | Standard ROS2 message types (Float64) |
| `rosidl_default_generators` | ROS2 IDL code generation |

## Building

The package is built automatically with the workspace:

```bash
cd ~/ros2_ws
colcon build --packages-select nectar_interfaces
source install/setup.bash
```

Verify:

```bash
ros2 interface list | grep nectar_interfaces
ros2 interface show nectar_interfaces/msg/ArucoTransforms
```

## Usage

**Python** — import, publish, and subscribe:

```python
from nectar_interfaces.msg import ArucoTransforms, LineInfo, PhotoInfo
from geometry_msgs.msg import Vector3
from std_msgs.msg import Float64

# Publisher
pub = node.create_publisher(ArucoTransforms, '/aruco/pose_estimate', 10)
msg = ArucoTransforms()
msg.id = 42
msg.translation = Vector3(x=0.5, y=0.1, z=1.2)
msg.yaw = Float64(data=45.0)
pub.publish(msg)

# Subscriber
def on_aruco(msg: ArucoTransforms):
    print(f"Marker {msg.id} at ({msg.translation.x:.2f}, {msg.translation.y:.2f}, {msg.translation.z:.2f}) m")

node.create_subscription(ArucoTransforms, '/aruco/pose_estimate', on_aruco, 10)
```

**C++**:

```cpp
#include "nectar_interfaces/msg/aruco_transforms.hpp"

auto pub = node->create_publisher<nectar_interfaces::msg::ArucoTransforms>(
    "/aruco/pose_estimate", 10);
```

## Related Modules

- [Vision Module](../nectar/nectar/vision/README.md) — camera drivers and algorithms that publish these messages
- [Vision Nodes](../nectar/nectar/vision/nodes/README.md) — ROS 2 nodes using these interfaces

## References

- [ROS2 Interfaces Tutorial](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html)
- [ROS2 Message Definition](https://docs.ros.org/en/humble/Concepts/About-ROS-Interfaces.html)
- [geometry_msgs](https://docs.ros.org/en/humble/p/geometry_msgs/)
- [std_msgs](https://docs.ros.org/en/humble/p/std_msgs/)
