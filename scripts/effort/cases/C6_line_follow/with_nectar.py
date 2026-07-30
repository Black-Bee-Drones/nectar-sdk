# @loc:boilerplate:begin
import math
import time

import nectar
from nectar.control import DroneFactory, MavrosConfig, PIDController, PoseSource
from nectar.vision import LineDetector, RotatedRect
from nectar.vision.camera import ImageHandler

# @loc:boilerplate:end
# @loc:core:begin
LINE_COLOR = "blue"
CENTER_TOL_PX = 25.0
LOST_LIMIT = 40
FOLLOW_TIMEOUT_S = 20.0
CRUISE_VX = 0.25
RATE = 1.0 / 30.0
# @loc:core:end
# @loc:boilerplate:begin

nectar.init()
drone = DroneFactory.create(
    "mavros", MavrosConfig(pose_source=PoseSource.VISION, start_driver=False)
)
line = LineDetector(color=LINE_COLOR, estimation_method=RotatedRect())
handler = ImageHandler("webcam")
handler.open()
# @loc:boilerplate:end
# @loc:core:begin

pid_y = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.35, 0.35)
)
pid_y.reset()

drone.takeoff(altitude=1.2)

# ACQUIRE
lost = 0
acquired = False
while True:
    frame = handler.take_photo()
    if frame is None:
        continue
    _img, _mask, cx, _cy, angle, _w, _h = line.detect_line(frame, draw=False)
    if not math.isnan(cx):
        acquired = True
        break
    lost += 1
    drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
    if lost >= LOST_LIMIT:
        break

# FOLLOW
lost = 0
t0 = time.time()
while acquired and time.time() - t0 < FOLLOW_TIMEOUT_S:
    frame = handler.take_photo()
    if frame is None:
        continue
    _img, _mask, cx, _cy, angle, _w, _h = line.detect_line(frame, draw=False)
    if math.isnan(cx):
        lost += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
        if lost >= LOST_LIMIT:
            break
        continue
    lost = 0
    h, w = frame.shape[:2]
    err_x = float(cx - w / 2.0)
    if abs(err_x) <= CENTER_TOL_PX:
        vy = 0.0
    else:
        vy = pid_y.update(err_x)
    drone.move_velocity(vx=CRUISE_VX, vy=vy, vz=0.0, duration=RATE)

drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
