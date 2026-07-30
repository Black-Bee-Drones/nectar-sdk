# @loc:boilerplate:begin
from nectar.ai.core import Framework
from nectar.ai.detection import Detector

# @loc:boilerplate:end
# @loc:core:begin
image_path = "image.jpg"
detector = Detector("rfdetr-medium", framework=Framework.RFDETR)
detector.load()
for det in detector.detect(image_path):
    print(det.class_name, det.confidence)
# @loc:core:end
