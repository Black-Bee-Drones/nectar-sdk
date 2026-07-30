# @loc:boilerplate:begin
from nectar.ai.classification import Classifier

# @loc:boilerplate:end
# @loc:core:begin
image_path = "image.jpg"
classifier = Classifier("yolov8n-cls.pt")
classifier.load()
cls = classifier.classify(image_path)
print(cls.top1_name, cls.top1_confidence)
# @loc:core:end
