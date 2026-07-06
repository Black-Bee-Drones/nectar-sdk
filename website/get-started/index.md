# Get started

Nectar SDK gives you one Python interface for three things a mission needs: **flying**,
**seeing**, and **detecting**, all sharing a single ROS 2 runtime. Pick a topic below, follow
the steps for your platform, camera, or model, and follow the links when you want the full
reference.

## The mental model

Every module follows the same shape, so once you know one you know them all:

```python
import nectar

nectar.init()                      # start the shared runtime (one background executor)
obj = SomeFactory.create(...)      # build a drone / camera / detector by key + config
obj.do_something(...)              # call the same API regardless of backend
nectar.shutdown()                  # stop the runtime
```

- **Factories** build the concrete backend from a string key and a typed config
  (`DroneFactory`, `CameraFactory`, `Detector`) — swap the key, keep the code.
- **One runtime** (`nectar.init` / `nectar.spin` / `nectar.shutdown`) owns a shared executor,
  so control, vision, and AI compose in a single mission. See [Architecture](../concepts/architecture.md).

## Prerequisites

A set-up Nectar SDK workspace. If you don't have one yet, do the [Installation](../setup/index.md)
first (it takes only the modules you choose). Each topic below lists the one module install it needs.

## Pick your path

<div class="grid cards" markdown>

-   **Fly a drone**

    Choose a platform and transport, start its driver or a simulator, configure a pose source,
    and fly a square — the same calls on ArduPilot, PX4, Crazyflie, or Bebop.

    [Fly a drone](control.md)

-   **See with a camera**

    Open any camera behind one factory, stream frames through an `ImageHandler`, and run an
    algorithm (ArUco, color, line, distance, MediaPipe).

    [See with a camera](vision.md)

-   **Detect & segment**

    Load a detection or segmentation model across Ultralytics YOLO, HuggingFace DETR, or
    RF-DETR behind one `Detector` / `Segmentor`, and run it on a frame.

    [Detect & segment](ai.md)

</div>

Each page is independent and shares the runtime, so you can compose them into a single
mission that flies, sees, and detects.
