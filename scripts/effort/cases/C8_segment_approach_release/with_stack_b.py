# @loc:boilerplate:begin
import time

import nectar
from nectar.ai.classification import Classifier
from nectar.ai.core import Framework
from nectar.ai.segmentation import Segmentor
from nectar.control import DroneFactory, PIDController, PoseSource, Px4MavlinkConfig
from nectar.vision.algorithms.distance import DistanceEstimator
from nectar.vision.camera import ImageHandler

nectar.init()
drone = DroneFactory.create(
    "px4_mavlink", Px4MavlinkConfig(pose_source=PoseSource.GPS, start_driver=False)
)
segmentor = Segmentor(
    "facebook/maskformer-swin-tiny-coco", framework=Framework.TRANSFORMERS
)
segmentor.load()
classifier = Classifier("google/vit-base-patch16-224", framework=Framework.TRANSFORMERS)
classifier.load()
handler = ImageHandler("/camera/color/image_raw")
handler.open()
_distance = DistanceEstimator(model_type="polynomial")


def get_range(cx: float, cy: float, pixel_h: float):
    del cx, cy  # geometric estimator uses bbox height
    cm = _distance.estimate(float(pixel_h))
    return float(cm) / 100.0


def hold_payload() -> None:
    drone.set_actuator(1, -1.0)


def release_payload() -> None:
    drone.set_actuator(1, 1.0)


# @loc:boilerplate:end
# @loc:core:begin
CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_SEG_CLASS = "person"
CONFIRM_LABEL = "person"
STANDOFF_M = 1.2
APPROACH_VX = 0.2
RATE = 1.0 / 30.0

pid_x = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_y = PIDController(
    kp=-0.002, ki=0.0, kd=0.0, setpoint=0.0, output_limits=(-0.4, 0.4)
)
pid_x.reset()
pid_y.reset()

drone.takeoff(altitude=1.5)

centered_seg = None
lost = 0
while True:
    handler.take_photo()
    frame = handler.img
    if frame is None:
        continue
    result = segmentor.segment(frame)
    targets = result.filter_by_class([TARGET_SEG_CLASS]) if result else None
    if not targets:
        lost += 1
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
        if lost >= LOST_LIMIT:
            break
        continue
    lost = 0
    seg = max(targets, key=lambda s: s.confidence)
    h, w = frame.shape[:2]
    cx, cy = seg.center
    err_x = float(cx - w / 2.0)
    err_y = float(cy - h / 2.0)
    if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
        drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
        centered_seg = seg
        break
    drone.move_velocity(
        vx=pid_y.update(err_y),
        vy=pid_x.update(-err_x),
        vz=0.0,
        duration=RATE,
    )

confirmed = False
if centered_seg is not None:
    handler.take_photo()
    frame = handler.img
    x1, y1, x2, y2 = [int(v) for v in centered_seg.xyxy]
    x1, y1 = max(0, x1), max(0, y1)
    crop = frame[y1:y2, x1:x2] if frame is not None else None
    if crop is not None and crop.size > 0:
        cls_result = classifier.classify(crop)
        confirmed = bool(cls_result) and cls_result.top1_name == CONFIRM_LABEL

approached = False
if confirmed:
    lost = 0
    while True:
        handler.take_photo()
        frame = handler.img
        if frame is None:
            continue
        result = segmentor.segment(frame)
        targets = result.filter_by_class([TARGET_SEG_CLASS]) if result else None
        if not targets:
            lost += 1
            drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=RATE)
            if lost >= LOST_LIMIT:
                break
            continue
        lost = 0
        seg = max(targets, key=lambda s: s.confidence)
        h, w = frame.shape[:2]
        cx, cy = seg.center
        err_x = float(cx - w / 2.0)
        range_m = get_range(cx, cy, float(seg.height))
        if range_m is not None and range_m <= STANDOFF_M:
            drone.move_velocity(vx=0.0, vy=0.0, vz=0.0, duration=0.2)
            approached = True
            break
        drone.move_velocity(
            vx=APPROACH_VX,
            vy=pid_x.update(-err_x),
            vz=0.0,
            duration=RATE,
        )

if approached:
    hold_payload()
    time.sleep(1.0)
    release_payload()
    time.sleep(1.0)

drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
