# @loc:boilerplate:begin
import nectar
from nectar.ai.core import Framework
from nectar.ai.detection import Detector
from nectar.control import DroneFactory, PIDController, PoseSource, Px4DdsConfig
from nectar.vision.camera import ImageHandler

nectar.init()
drone = DroneFactory.create(
    "px4_dds", Px4DdsConfig(pose_source=PoseSource.GPS, start_driver=False)
)
detector = Detector("facebook/detr-resnet-50", framework=Framework.TRANSFORMERS)
detector.load()
handler = ImageHandler(
    "realsense",
    image_processing_callback=lambda frame: detector.detect(frame),
)
handler.open()
# @loc:boilerplate:end
# @loc:core:begin
CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_CLASS = "person"
RATE = 1.0 / 30.0

drone.takeoff(altitude=1.2)

pid_x = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_y = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_x.reset()
pid_y.reset()

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
    if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
        break
    drone.move_velocity(
        vx=pid_y.update(err_y),
        vy=pid_x.update(-err_x),
        vz=0.0,
        duration=RATE,
    )

drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
