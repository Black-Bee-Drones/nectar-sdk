# @loc:boilerplate:begin
#!/usr/bin/env python3
import sys

import cv2
import torch
from PIL import Image as PILImage
from transformers import AutoImageProcessor, AutoModelForObjectDetection


def main(image_path: str) -> None:
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise RuntimeError(f"cannot read {image_path}")
    pil = PILImage.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    processor = AutoImageProcessor.from_pretrained("facebook/detr-resnet-50")
    model = AutoModelForObjectDetection.from_pretrained("facebook/detr-resnet-50")
    model.eval()
    inputs = processor(images=pil, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    # @loc:boilerplate:end
    # @loc:core:begin
    results = processor.post_process_object_detection(
        outputs, threshold=0.25, target_sizes=torch.tensor([pil.size[::-1]])
    )[0]
    id2label = model.config.id2label
    for score, label in zip(results["scores"], results["labels"]):
        print(f"{id2label[label.item()]}: {score.item():.2f}")


# @loc:core:end
# @loc:boilerplate:begin


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
# @loc:boilerplate:end
