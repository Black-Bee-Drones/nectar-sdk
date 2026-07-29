# @loc:boilerplate:begin
from nectar.ai.segmentation import Segmentor

image_path = "image.jpg"
# @loc:boilerplate:end
# @loc:core:begin
segmentor = Segmentor("yolov8n-seg.pt")
segmentor.load()
for seg in segmentor.segment(image_path):
    print(seg.class_name, seg.confidence, seg.mask_area)
# @loc:core:end
