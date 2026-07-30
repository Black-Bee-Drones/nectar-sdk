# @loc:boilerplate:begin
#!/usr/bin/env python3
import sys

import cv2
from ultralytics import YOLO


def main(image_path: str) -> None:
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"cannot read {image_path}")
    model = YOLO("yolov8n-cls.pt")
    # @loc:boilerplate:end
    # @loc:core:begin
    out = model.predict(image, verbose=False)[0]
    names = out.names
    top1 = int(out.probs.top1)
    conf = float(out.probs.top1conf)
    print(f"{names[top1]}: {conf:.2f}")


# @loc:core:end
# @loc:boilerplate:begin


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
# @loc:boilerplate:end
