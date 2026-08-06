# Indoor flight — practical guide

Day-of-flight procedure for the **current** indoor stack: RealSense **D435i** +
**Isaac ROS Visual SLAM (cuVSLAM)** on a Jetson Orin Nano, pose bridged into
ArduPilot or PX4 through Nectar.

This page is **procedure and tips**. Launch commands, FCU parameter tables,
backends, SITL, and RViz launch arguments live in the
[Localization README](README.md) — do not duplicate them here. Theory:
[Concepts](concepts.md). Older T265 workflow: [Legacy T265](legacy.md).

Topology: [README → Topology](README.md#topology).

---

## Before you power on

### FCU already configured

External-nav parameters and EKF origin requirements are in
[FCU setup](README.md#fcu-setup). For ArduPilot indoor hardware we fly today:
`VISO_TYPE=1`, `EK3_SRC1_POSXY/POSZ/YAW=6`, `GPS1_TYPE=0` (and velocity sources
only if you enable `send_speed:=true`). Reboot the FCU after changing these.

Height: prefer vision Z indoors unless you deliberately want terrain following
with a rangefinder — see [Height source](README.md#height-source).

### Mechanical mounting (*Black Bee practice*)

VIO / V-SLAM assume the camera and IMU move with the airframe, not relative to
it. Vibration and a loose mount look like motion to the estimator.

- Mount the D435i so the optical axis matches the extrinsics you configured
  (`VISO_POS_*` / Isaac launch frames).
- Secure the camera: rubber bands and foam between the camera and the frame to
  damp high-frequency vibration; foam inside the sensor case where it helps
  without blocking lenses or the USB connector.
- Recheck fasteners after transport. After any significant remount, restart the
  producer and bridge and re-run the checks below — do not assume yesterday's
  map session is still valid.

### Network / domain

Jetson (producer), companion or host (bridge), and optional laptop (RViz) must
share the same `ROS_DOMAIN_ID` (default `14` — see `scripts/lib/config.sh`).

---

## Bring-up order

Commands: [README → Run](README.md#run) and the Isaac section of the
[Docker guide](../../../../docker/README.md#isaac-ros-visual-slam-jetson).

1. **Producer (Jetson)** — enter the Isaac container (`make isaac-run` /
   `nectar-vslam`). Confirm RealSense enumerates and VSLAM topics publish.
2. **Consumer (companion / host)** — start the vision-pose bridge for your
   transport (`./setup.sh driver … --env indoor` or
   `ros2 launch nectar vision_pose.launch.py …`). Respect the
   [one feeder rule](README.md#one-feeder-rule): do not also start a second
   vision feeder on the same FCU link from a mission.
3. **Verify the pipeline** — [README checks](README.md) and
   `vision_fcu_check.py` (fused FCU local pose + optional ROS rates). Move the
   airframe by hand; fused position must change.
4. **Set EKF origin** — Mission Planner *Set EKF Origin Here*, QGC equivalent,
   `SET_GPS_GLOBAL_ORIGIN`, or your usual script. Without an origin and with
   GPS disabled, position modes will not engage correctly
   ([ArduPilot non-GPS docs](https://ardupilot.org/dev/docs/mavlink-nongps-position-estimation.html)).
5. **Visualization / warm-up** (next section), then flight modes.

If the system has been powered for a long time, or you changed mounts / USB /
parameters, **restart producer + bridge** before flying. Odd GCS warnings and
stale EKF behaviour often clear after a clean restart (*Black Bee practice*).

---

## Visualization and map warm-up

RViz (or the GCS vehicle icon) shows the **SLAM / odometry path**. That display
is a **quality check**, not a calibration wizard: it does not set camera
intrinsics or body extrinsics.

Use it to answer:

- Does the path track real motion without obvious jumps?
- When you return near a place you already visited, does the green SLAM path
  snap consistently with loop closure (see
  [Visualization](README.md#visualization))?
- Is noise low enough that Loiter could hold?

### Warm-up motion (*Black Bee practice*)

Before arming for the mission, move the drone slowly through the volume it will
fly — a hand-carried square, circle, or walk-around of the arena:

- Gives cuVSLAM time to build a larger map and register landmarks.
- Lets you judge estimate quality while you can still abort on the ground.
- Improves later flight when the vehicle revisits known structure and loop
  closure can correct drift.

Keep motions **smooth**. Avoid abrupt translations and fast yaw. Do not walk
rapidly across the camera FOV or wave objects in front of the lens during
bring-up — dynamic clutter hurts matching
([Concepts → Failure modes](concepts.md#failure-modes-practical)).

Run RViz on a **laptop**, not on the Jetson, so visualization does not steal
GPU/CPU from tracking
([NVIDIA RealSense tutorial](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/tutorial_realsense.html)).
Launch lines: [README → Visualization](README.md#visualization).

---

## Scale and vertical check

With the T265, ArduPilot / community bring-up (and our team notes) recommended
lifting the vehicle about **one meter** off the ground and setting it down again
before flight so vertical motion exercised metric scale — see
[Legacy T265](legacy.md) and ArduPilot's
[T265 / VIO pages](https://ardupilot.org/copter/docs/common-vio-tracking-camera.html).

With D435i + cuVSLAM the same idea still applies as a **sanity check**, not as
a hidden calibration button:

- After origin is set, lift and translate the airframe by hand.
- Confirm fused local pose (GCS or `vision_fcu_check.py`) moves roughly the
  right distance in X/Y/Z.
- If vertical motion is wrong or sticky, fix height source / bridge / mounting
  before trusting Loiter.

---

## First flight

Aligns with LuckyBird's T265 flight-test advice and our indoor checklist
([Discourse part 2](https://discuss.ardupilot.org/t/integration-of-ardupilot-and-vio-tracking-camera-part-2-complete-installation-and-indoor-non-gps-flights/43405)):

1. Confirm vision is live on the GCS (vehicle icon moves when you move the
   frame; MAVLink Inspector shows vision / local position updating).
2. Take off in **Stabilize** or **AltHold**. Confirm the vehicle is controllable.
3. Move gently; watch fused position on the GCS (and RViz if open).
4. Switch to **Loiter** only when tracking looks stable — be ready to drop back
   to Stabilize/AltHold immediately.
5. Translate a few meters and yaw slowly; verify scale and that the hold does
   not oscillate or walk off.
6. Only then fly the mission or more aggressive profiles.

Optional companion mission examples use `--env indoor` /
`PoseSource.VISION` — see [README](README.md) and the control examples under
`nectar/examples/control/`.

---

## Failure triage

| Symptom | Likely cause | What to try |
|---------|--------------|-------------|
| No VSLAM topics | Camera / Isaac producer / USB | `rs-enumerate-devices` in the Isaac container; USB3; restart `nectar-vslam`; see [Docker Isaac notes](../../../../docker/README.md#isaac-ros-visual-slam-jetson) |
| VSLAM OK, FCU pose frozen | Bridge down, wrong domain, or one-feeder conflict | Shared `ROS_DOMAIN_ID`; restart consumer; [one feeder rule](README.md#one-feeder-rule) |
| Vision on ROS, EKF not using it | Params / origin | [FCU setup](README.md#fcu-setup); set EKF origin; reboot after param changes |
| Jumpy or diverging path | Vibration, texture, abrupt motion, stale session | Soft-mount; slower warm-up; restart producer after long idle or remount |
| Loiter oscillates / walks | Delay or noise tuning; velocity double-count | Tune `VISO_DELAY_MS` / noise; leave `send_speed` off unless logs show benefit ([Velocity](README.md#velocity-optional)) |
| Strange GCS flags after long power-on | Stale nodes / EKF state | Power-cycle or restart FCU + producer + bridge (*Black Bee practice*) |

---

## See also

- [Localization README](README.md) — architecture, Run, FCU, backends, SITL, RViz commands
- [Concepts](concepts.md) — SLAM / VIO / V-SLAM and EKF fusion
- [Legacy T265](legacy.md) — 2023–2024 `vision_to_mavros` path
- [RealSense setup](../../../../docs/setup/realsense.md) — librealsense / realsense-ros install
- [Docker → Isaac ROS Visual SLAM](../../../../docker/README.md#isaac-ros-visual-slam-jetson)
