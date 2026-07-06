# Vision Module

Camera abstraction layer and image-processing algorithms for ROS 2. One `CameraFactory` opens any
supported camera behind a common interface, an `ImageHandler` turns it into a callback-driven
stream, and a set of algorithms (ArUco, color, line, distance, MediaPipe) run on the frames.

## At a glance

```python
import nectar
from nectar.vision.camera import ImageHandler

nectar.init()
ImageHandler("webcam", image_processing_callback=lambda frame: print(frame.shape)).run()
nectar.spin()
nectar.shutdown()
```

Need a single frame instead of a stream?

```python
from nectar.vision import CameraFactory

cam = CameraFactory.from_source("webcam")
cam.start()
frame = cam.get_frame()
cam.close()
```

## Documentation

| Page | Scope |
|------|-------|
| [Cameras](camera/README.md) | `CameraFactory`, `ImageHandler`, `AbstractCam`/`DepthCam`, drivers, configs, T265, calibration, image geometry |
| [Algorithms](algorithms/README.md) | ArUco, color, line, distance regression, MediaPipe hand/face, optical flow |
| [ROS 2 nodes](nodes/README.md) | ArUco, line detection, color calibration, and camera publisher nodes |

## Concepts

Two layers sit behind the module:

- **Cameras.** `CameraFactory.from_source(key)` returns a driver implementing `AbstractCam`
  (`start` / `get_frame` / `close`); depth-capable cameras add `DepthCam` (`get_depth_frame` /
  `get_distance`). See [Cameras](camera/README.md).
- **Streaming + algorithms.** `ImageHandler` wraps any camera in a timer-driven ROS 2 node and
  calls your processing callback on each frame. The callback runs an [algorithm](algorithms/README.md)
  (ArUco, color, line, distance, MediaPipe), or you can run the ready-made
  [ROS 2 nodes](nodes/README.md).

Both share the SDK runtime executor (see [`nectar.runtime`](../runtime.py)), so vision composes
with control and AI in one mission.

## Examples

See `examples/vision/` for complete working scripts:

| Example | Description |
|---------|-------------|
| `camera_example.py` | Basic camera capture and configuration |
| `depth_example.py` | Depth camera visualization and distance (RealSense D4xx, OAK-D) |
| `t265_example.py` | T265 fisheye + stereo depth + pose overlay + click-to-measure |
| `optical_flow_example.py` | Sparse/dense optical-flow visualization |
| `collect_photos.py` | Save frames at intervals for dataset creation |

## Extending the module

- Camera drivers: add to `camera/drivers/`, inherit `AbstractCam` or `DepthCam`, add a config
  dataclass in `camera/config.py`, and register it with `CameraFactory.register()` in
  `camera/factory.py`.
- Algorithms: add to `algorithms/<category>/`.
- ROS 2 nodes: add to `nodes/`.
- Export public symbols in `__init__.py`.
