# @loc:boilerplate:begin
import nectar
from nectar.ai.detection import Detector
from nectar.control import DroneFactory, MavlinkConfig, PIDController, PoseSource
from nectar.vision.camera import ImageHandler

# @loc:boilerplate:end
# @loc:core:begin
N_GATES = 2
GATE_CLASS = "gate"
CENTER_PX = 40.0
CENTER_CONFIRM = 3
LOST_LIMIT = 30
SEARCH_STEP_M = 0.4
SEARCH_STEPS = 6
PASS_M = 1.5
RATE = 1.0 / 30.0
# @loc:core:end
# @loc:boilerplate:begin

nectar.init()
drone = DroneFactory.create(
    "mavlink", MavlinkConfig(pose_source=PoseSource.VISION, start_driver=False)
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


def best_gate(result):
    if not result:
        return None
    targets = result.filter_by_class([GATE_CLASS])
    if not targets:
        return None
    return max(targets, key=lambda d: d.confidence)


def search_gate():
    for step in range(SEARCH_STEPS):
        result = handler.take_photo()
        if best_gate(result) is not None:
            return True
        # Lateral sweep then small climb every other step.
        vy = SEARCH_STEP_M if (step % 2 == 0) else -SEARCH_STEP_M
        vz = 0.15 if (step % 4 == 3) else 0.0
        drone.move_velocity(vx=0.0, vy=vy, vz=vz, duration=0.8)
    return False


def align_gate():
    pid_x = PIDController(
        kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
    )
    pid_y = PIDController(
        kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
    )
    pid_x.reset()
    pid_y.reset()
    confirms = 0
    lost = 0
    while True:
        result = handler.take_photo()
        det = best_gate(result)
        if det is None:
            lost += 1
            drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
            if lost >= LOST_LIMIT:
                return False
            continue
        lost = 0
        h, w = handler.img.shape[:2]
        cx, cy = det.center
        err_x = float(cx - w / 2.0)
        err_y = float(cy - h / 2.0)
        if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
            confirms += 1
            drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
            if confirms >= CENTER_CONFIRM:
                return True
            continue
        confirms = 0
        drone.move_velocity(
            vx=pid_y.update(err_y),
            vy=pid_x.update(-err_x),
            vz=0.0,
            duration=RATE,
        )


def pass_gate():
    drone.move_velocity(vx=PASS_M / 2.0, vy=0.0, vz=0.0, duration=2.0)
    drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)


drone.takeoff(altitude=1.2)
for _ in range(N_GATES):
    if not search_gate():
        break
    if not align_gate():
        break
    pass_gate()
drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
