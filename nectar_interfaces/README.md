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

**Published by:** `ArucoNode`

**Topic:** `/aruco/pose_estimate`

**Usage Example:**

```python
from nectar_interfaces.msg import ArucoTransforms
from geometry_msgs.msg import Vector3
from std_msgs.msg import Float64

msg = ArucoTransforms()
msg.id = 42
msg.translation = Vector3(x=0.5, y=0.1, z=1.2)
msg.yaw = Float64(data=45.0)

publisher.publish(msg)
```

**Subscriber Example:**

```python
def aruco_callback(msg: ArucoTransforms):
    marker_id = msg.id
    x, y, z = msg.translation.x, msg.translation.y, msg.translation.z
    yaw_degrees = msg.yaw.data

    print(f"Marker {marker_id} at ({x:.2f}, {y:.2f}, {z:.2f})m, yaw={yaw_degrees:.1f}°")

node.create_subscription(ArucoTransforms, '/aruco/pose_estimate', aruco_callback, 10)
```

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

**Published by:** `LineDetectionNode`

**Topic:** `line_state/{color}` (e.g., `line_state/blue`)

**Usage Example:**

```python
from nectar_interfaces.msg import LineInfo

msg = LineInfo()
msg.center_x = 320.5
msg.center_y = 240.0
msg.angle = -15.3
msg.width = 25.0
msg.height = 180.0

publisher.publish(msg)
```

**Subscriber Example:**

```python
def line_callback(msg: LineInfo):
    if msg.angle != float('nan'):
        print(f"Line at ({msg.center_x:.1f}, {msg.center_y:.1f})")
        print(f"Angle: {msg.angle:.1f}°, Width: {msg.width:.1f}px")

node.create_subscription(LineInfo, 'line_state/blue', line_callback, 10)
```

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

**Usage Example:**

```python
from nectar_interfaces.msg import PhotoInfo

msg = PhotoInfo()
msg.coordinates = [27.1234, -48.5678, 15.0]  # lat, lon, alt
msg.photo_num = "IMG_001"

publisher.publish(msg)
```

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

## Verifying Installation

```bash
# List available messages
ros2 interface list | grep nectar_interfaces

# Show message definition
ros2 interface show nectar_interfaces/msg/ArucoTransforms
ros2 interface show nectar_interfaces/msg/LineInfo
ros2 interface show nectar_interfaces/msg/PhotoInfo
```

## Using in Python

```python
# Import messages
from nectar_interfaces.msg import ArucoTransforms, LineInfo, PhotoInfo

# Create publisher
aruco_pub = node.create_publisher(ArucoTransforms, '/aruco/pose_estimate', 10)
line_pub = node.create_publisher(LineInfo, 'line_state/blue', 10)
```

## Using in C++

```cpp
#include "nectar_interfaces/msg/aruco_transforms.hpp"
#include "nectar_interfaces/msg/line_info.hpp"
#include "nectar_interfaces/msg/photo_info.hpp"

auto aruco_pub = node->create_publisher<nectar_interfaces::msg::ArucoTransforms>(
    "/aruco/pose_estimate", 10);
```

## Package Structure

```
nectar_interfaces/
├── CMakeLists.txt          # Build configuration
├── package.xml             # Package manifest
├── LICENSE                 # Apache-2.0
├── README.md               # This file
└── msg/
    ├── ArucoTransforms.msg # ArUco pose message
    ├── LineInfo.msg        # Line detection message
    └── PhotoInfo.msg       # Photo metadata message
```

---

## Related Modules

- [Vision Module](../nectar/nectar/vision/README.md) - Camera drivers and detection algorithms that publish these messages
- [Vision Nodes](../nectar/nectar/vision/nodes/) - ROS2 nodes using these interfaces

## References

- [ROS2 Interfaces Tutorial](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Custom-ROS2-Interfaces.html)
- [ROS2 Message Definition](https://docs.ros.org/en/humble/Concepts/About-ROS-Interfaces.html)
- [geometry_msgs](https://docs.ros.org/en/humble/p/geometry_msgs/)
- [std_msgs](https://docs.ros.org/en/humble/p/std_msgs/)
