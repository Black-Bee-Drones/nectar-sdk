# @loc:boilerplate:begin
import time

import nectar
from nectar.ai.detection import Detector
from nectar.control import DroneFactory, MavrosConfig, NavigationMethod, PoseSource
from nectar.vision.camera import ImageHandler

# @loc:boilerplate:end
# @loc:core:begin
WAYPOINTS = [
    (5.0, 0.0, 0.0),
    (5.0, 5.0, 0.0),
    (0.0, 5.0, 0.0),
    (0.0, 0.0, 0.0),
]
HOVER_S = 2.0
DETECT_CLASS = None  # None = log all classes
# @loc:core:end
# @loc:boilerplate:begin

nectar.init()
drone = DroneFactory.create(
    "mavros", MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
)
detector = Detector("yolov8n.pt")
detector.load()
handler = ImageHandler(
    "/camera/color/image_raw",
    image_processing_callback=lambda frame: detector.detect(frame),
)
handler.open()
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=2.0)

detections_log = []
for dx, dy, dz in WAYPOINTS:
    drone.move_to(x=dx, y=dy, z=dz, precision=0.4, method=NavigationMethod.POSITION)
    deadline = time.time() + HOVER_S
    while time.time() < deadline:
        result = handler.take_photo()
        if not result:
            continue
        dets = (
            result if DETECT_CLASS is None else result.filter_by_class([DETECT_CLASS])
        )
        for det in dets or []:
            detections_log.append((det.class_name, float(det.confidence)))

drone.land()
# @loc:core:end
# @loc:boilerplate:begin
handler.cleanup()
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
