# @loc:boilerplate:begin
#!/usr/bin/env python3
import sys

import cv2
from PIL import Image as PILImage
from rfdetr import RFDETRMedium


def main(image_path: str) -> None:
    bgr = cv2.imread(image_path)
    if bgr is None:
        raise RuntimeError(f"cannot read {image_path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    model = RFDETRMedium()
    # @loc:boilerplate:end
    # @loc:core:begin
    detections = model.predict(PILImage.fromarray(rgb), threshold=0.25)
    for i in range(len(detections)):
        cls_id = int(detections.class_id[i])
        conf = float(detections.confidence[i])
        print(f"{cls_id}: {conf:.2f}")


# @loc:core:end
# @loc:boilerplate:begin


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
# @loc:boilerplate:end
