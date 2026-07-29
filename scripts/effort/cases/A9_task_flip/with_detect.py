# @loc:boilerplate:begin
from nectar.ai.detection import Detector

image_path = "image.jpg"
# @loc:boilerplate:end
# @loc:core:begin
detector = Detector("yolov8n.pt")
detector.load()
for det in detector.detect(image_path):
    print(det.class_name, det.confidence)
# @loc:core:end
