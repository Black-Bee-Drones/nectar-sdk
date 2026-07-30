# @loc:boilerplate:begin
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
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=1.2)

aruco = Aruco(marker_dict=5, tag_size=0.2)
handler = ImageHandler(
    "/camera/color/image_raw",
    image_processing_callback=lambda frame: aruco.pose_estimate(frame),
)
handler.open()

pid_x = PIDController(
    kp=-0.4, ki=-0.02, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_y = PIDController(
    kp=-0.4, ki=-0.02, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
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
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
