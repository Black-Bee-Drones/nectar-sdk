# @loc:boilerplate:begin
#!/usr/bin/env python3
import depthai as dai


def main() -> None:
    pipeline = dai.Pipeline()
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    xout = pipeline.create(dai.node.XLinkOut)
    xout.setStreamName("rgb")
    cam_rgb.video.link(xout.input)
    with dai.Device(pipeline) as device:
        queue = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        # @loc:boilerplate:end
        # @loc:core:begin
        frame = queue.get().getCvFrame()
        if frame is None:
            raise RuntimeError("failed to read frame")
        print(frame.shape)
        # @loc:core:end
        # @loc:boilerplate:begin


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
