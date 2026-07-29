# @loc:boilerplate:begin
from nectar.ai.detection import Detector

# @loc:boilerplate:end
# @loc:core:begin
detector = Detector("yolov8n.pt")
detector.load()
result = detector.detect("image.jpg")
for det in result:
    print(f"{det.class_name}: {det.confidence:.2f}")
# @loc:core:end
