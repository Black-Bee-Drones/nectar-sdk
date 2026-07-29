# @loc:boilerplate:begin
#!/usr/bin/env python3
import cv2


def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("cannot open webcam")
    # @loc:boilerplate:end
    # @loc:core:begin
    ok, frame = cap.read()
    if not ok or frame is None:
        raise RuntimeError("failed to read frame")
    print(frame.shape)
    # @loc:core:end
    # @loc:boilerplate:begin
    cap.release()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
