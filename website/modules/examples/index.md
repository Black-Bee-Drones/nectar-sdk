# Examples

Runnable scripts that live next to the code in `nectar/nectar/examples/`, grouped by the
module they exercise. Each one is small, self-contained, and meant to be read as much as
run — start here to see how the modules are used and combined in practice.

| Group | What it covers |
|-------|----------------|
| [Control](control.md) | Takeoff/land, velocity and position flight, navigation test suites, interactive REPL, PID, servo/PWM, obstacle-aware navigation |
| [Vision](vision.md) | Camera drivers, depth measurement, T265 tracking, optical flow, dataset photo collection |
| [AI](ai.md) | Real-time detection stream, batch image/video processing, multi-model detection + segmentation |
| [Sensors](sensors.md) | TF-Luna rangefinder → MAVLink bridge bench test |

## How to run

Every example uses `argparse`. Run from the repo with:

```bash
python3 nectar/nectar/examples/<group>/<script>.py [flags]
```

Some scripts are also installed as ROS 2 executables (see each group's page for which
ones): `ros2 run nectar <script>.py -- [flags]`. Control examples are **not** installed —
use `python3` only.

Control examples default to `start_driver=False` — start the driver/bridge (or the
simulator) the mission connects to first, in its own terminal. See
[Fly a drone](../../get-started/control.md) for the simulation and hardware flow.
