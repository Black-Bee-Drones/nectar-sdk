# @loc:boilerplate:begin
from nectar.ai.core import Framework
from nectar.ai.detection import Detector

# @loc:boilerplate:end
# @loc:core:begin
image_path = "image.jpg"
for model, framework in (
    ("yolov8n.pt", None),
    ("rfdetr-medium", None),
    ("facebook/detr-resnet-50", Framework.TRANSFORMERS),
):
    detector = Detector(model, framework=framework)
    detector.load()
    for det in detector.detect(image_path):
        print(model, det.class_name, det.confidence)
# @loc:core:end
