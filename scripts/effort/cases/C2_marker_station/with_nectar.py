# @loc:boilerplate:begin
import nectar
from nectar.control import DroneFactory, MavrosConfig, PIDController, PoseSource
from nectar.vision import Aruco
from nectar.vision.camera import ImageHandler

# @loc:boilerplate:end
# @loc:core:begin
CENTER_XY = 0.05
STANDOFF_M = 1.0
TOL_M = 0.15
LOST_LIMIT = 30
SETTLE_CONFIRM = 3
APPROACH_GAIN = 0.3
RATE = 1.0 / 30.0
# @loc:core:end
# @loc:boilerplate:begin

nectar.init()
drone = DroneFactory.create(
    "mavros", MavrosConfig(pose_source=PoseSource.VISION, start_driver=False)
)
aruco = Aruco(marker_dict=5, tag_size=0.2)
handler = ImageHandler(
    "/camera/color/image_raw",
    image_processing_callback=lambda frame: aruco.pose_estimate(frame),
)
handler.open()
# @loc:boilerplate:end
# @loc:core:begin

pid_x = PIDController(
    kp=-0.4, ki=-0.02, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_y = PIDController(
    kp=-0.4, ki=-0.02, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_x.reset()
pid_y.reset()

drone.takeoff(altitude=1.2)

# SEARCH
lost = 0
tvec = None
while True:
    out = handler.take_photo()
    if out is None:
        continue
    marker_id, tvec, _yaw = out
    if marker_id is not None and tvec is not None:
        break
    lost += 1
    drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
    if lost >= LOST_LIMIT:
        tvec = None
        break

phase = "center"
settles = 0
lost = 0
while tvec is not None:
    out = handler.take_photo()
    if out is None:
        continue
    marker_id, tvec, _yaw = out
    if marker_id is None or tvec is None:
        lost += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
        if lost >= LOST_LIMIT:
            break
        continue
    lost = 0
    err_x, err_y, err_z = float(tvec[0]), float(tvec[1]), float(tvec[2])
    centered = err_x * err_x + err_y * err_y <= CENTER_XY * CENTER_XY
    range_err = float(err_z - STANDOFF_M)
    in_band = centered and abs(range_err) <= TOL_M

    if phase == "center":
        if centered:
            phase = "approach"
        else:
            drone.move_velocity(
                vx=pid_x.update(err_x),
                vy=pid_y.update(err_y),
                vz=0.0,
                duration=RATE,
            )
            continue

    if phase == "approach":
        if in_band:
            phase = "settle"
            settles = 0
        else:
            vx = APPROACH_GAIN * range_err if centered else pid_x.update(err_x)
            drone.move_velocity(
                vx=vx,
                vy=pid_y.update(err_y),
                vz=0.0,
                duration=RATE,
            )
            continue

    # settle
    if in_band:
        settles += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
        if settles >= SETTLE_CONFIRM:
            break
    else:
        settles = 0
        phase = "approach" if centered else "center"

drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
