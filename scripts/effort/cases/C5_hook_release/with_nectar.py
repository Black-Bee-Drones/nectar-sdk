# @loc:boilerplate:begin
import time

import nectar
from nectar.ai.detection import Detector
from nectar.control import DroneFactory, MavrosConfig, PIDController, PoseSource
from nectar.vision.camera import ImageHandler

# @loc:boilerplate:end
# @loc:core:begin
TARGET_CLASS = "sphere"
CENTER_PX = 40.0
LOST_LIMIT = 30
APPROACH_RATIO = 0.25
SERVO_CHANNEL = 1
HOLD_PWM = 1000
RELEASE_PWM = 2000
RATE = 1.0 / 30.0
# @loc:core:end
# @loc:boilerplate:begin

nectar.init()
drone = DroneFactory.create(
    "mavros", MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
)
detector = Detector("yolov8n.pt")
detector.load()
handler = ImageHandler(
    "webcam",
    image_processing_callback=lambda frame: detector.detect(frame),
)
handler.open()
# @loc:boilerplate:end
# @loc:core:begin

pid_x = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_y = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_x.reset()
pid_y.reset()

drone.takeoff(altitude=1.5)

phase = "center"
lost = 0
while True:
    result = handler.take_photo()
    targets = result.filter_by_class([TARGET_CLASS]) if result else None
    if not targets:
        lost += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
        if lost >= LOST_LIMIT:
            break
        continue
    lost = 0
    det = max(targets, key=lambda d: d.confidence)
    h, w = handler.img.shape[:2]
    cx, cy = det.center
    err_x = float(cx - w / 2.0)
    err_y = float(cy - h / 2.0)
    # Range proxy: bbox height over image height (larger => closer).
    x1, y1, x2, y2 = det.xyxy
    ratio = abs(float(y2 - y1)) / float(h)

    if phase == "center":
        if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
            phase = "approach"
        else:
            drone.move_velocity(
                vx=pid_y.update(err_y),
                vy=pid_x.update(-err_x),
                vz=0.0,
                duration=RATE,
            )
            continue

    if phase == "approach":
        if (
            ratio >= APPROACH_RATIO
            and err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX
        ):
            phase = "release"
            break
        drone.move_velocity(
            vx=0.2,
            vy=pid_x.update(-err_x),
            vz=0.0,
            duration=RATE,
        )

drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
if phase == "release":
    drone.do_servo(SERVO_CHANNEL, HOLD_PWM)
    time.sleep(1.0)
    drone.do_servo(SERVO_CHANNEL, RELEASE_PWM)
    time.sleep(1.0)

drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
