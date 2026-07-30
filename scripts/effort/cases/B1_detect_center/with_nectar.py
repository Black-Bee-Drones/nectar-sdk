# @loc:boilerplate:begin
import nectar
from nectar.ai.detection import Detector
from nectar.control import DroneFactory, MavlinkConfig, PIDController, PoseSource
from nectar.vision.camera import ImageHandler

CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_CLASS = "person"  # class name in the loaded model

nectar.init()
drone = DroneFactory.create(
    "mavlink", MavlinkConfig(pose_source=PoseSource.VISION, start_driver=False)
)
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=1.2)

detector = Detector("yolov8n.pt")
detector.load()

handler = ImageHandler(
    "webcam",
    image_processing_callback=lambda frame: detector.detect(frame),
)
handler.open()

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
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=1.0 / 30.0)
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
    # Downward camera: image x → body vy, image y → body vx (signs are mission-tuned).
    drone.move_velocity(
        vx=pid_y.update(err_y),
        vy=pid_x.update(-err_x),
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
