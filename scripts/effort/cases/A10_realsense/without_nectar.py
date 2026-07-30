# @loc:boilerplate:begin
#!/usr/bin/env python3
import numpy as np
import pyrealsense2 as rs


def main() -> None:
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    pipeline.start(config)
    try:
        # @loc:boilerplate:end
        # @loc:core:begin
        frames = pipeline.wait_for_frames(timeout_ms=5000)
        color = np.asanyarray(frames.get_color_frame().get_data())
        if color is None or color.size == 0:
            raise RuntimeError("failed to read frame")
        print(color.shape)
        # @loc:core:end
        # @loc:boilerplate:begin
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
