# @loc:boilerplate:begin
from nectar.ai.detection import Detector
from nectar.ai.segmentation import Segmentor
from nectar.ai.classification import Classifier

image_path = "image.jpg"

# @loc:boilerplate:end
# @loc:core:begin
detector = Detector("yolov8n.pt")
detector.load()
for det in detector.detect(image_path):
    print(det.class_name, det.confidence)

segmentor = Segmentor("yolov8n-seg.pt")
segmentor.load()
for seg in segmentor.segment(image_path):
    print(seg.class_name, seg.confidence, seg.mask_area)

classifier = Classifier("yolov8n-cls.pt")
classifier.load()
cls = classifier.classify(image_path)
print(cls.top1_name, cls.top1_confidence)
# @loc:core:end
