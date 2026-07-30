# @loc:boilerplate:begin
#!/usr/bin/env python3
import sys

import cv2
from ultralytics import YOLO


def main(image_path: str) -> None:
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"cannot read {image_path}")
    model = YOLO("yolov8n.pt")
    # @loc:boilerplate:end
    # @loc:core:begin
    out = model.predict(image, conf=0.25, verbose=False)[0]
    names = out.names
    for box in out.boxes:
        cls_id = int(box.cls.item())
        conf = float(box.conf.item())
        print(f"{names[cls_id]}: {conf:.2f}")


# @loc:core:end
# @loc:boilerplate:begin


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "image.jpg")
# @loc:boilerplate:end
