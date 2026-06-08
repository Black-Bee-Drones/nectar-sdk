#!/usr/bin/env python3
import argparse
import logging

import nectar
from nectar.vision.camera import ImageHandler
from nectar.vision.camera.config_builder import ConfigBuilder

log = logging.getLogger("camera_example")


_CAMERA_PARAMS = {
    "webcam": {"device_index": 0, "width": 1280, "height": 720, "fps": 30},
    "imx219": {"sensor_id": 0, "width": 1280, "height": 720, "flip": 2},
    "realsense": {
        "color_width": 1280,
        "color_height": 720,
        "depth_width": 1280,
        "depth_height": 720,
        "fps": 30,
    },
    "c920": {"profile": 1},
    "oakd": {},
    "ros": {
        "topic": "/camera/color/image_raw/compressed",
        "compressed": True,
    },
    "realsense_ros": {
        "topic": "/camera/color/image_raw/compressed",
        "compressed": True,
        "depth_topic": "/camera/depth/image_rect_raw",
        "depth_compressed": False,
    },
}


def build_camera_config(camera_type: str):
    """Return (config, source_key) for the requested camera type."""
    source_key = "ros_depth" if camera_type == "realsense_ros" else camera_type
    params = _CAMERA_PARAMS.get(camera_type)
    if params is None:
        return None, camera_type
    return ConfigBuilder.build(source_key, params), source_key


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Camera example using ImageHandler")
    parser.add_argument("--camera-type", default="webcam", choices=list(_CAMERA_PARAMS))
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    nectar.init()
    config, source = build_camera_config(args.camera_type)
    count = [0]

    def on_frame(frame) -> None:
        if frame is None:
            return
        count[0] += 1
        log.info("Received frame %d with shape: %s", count[0], frame.shape)

    handler = ImageHandler(
        image_source=source,
        config=config,
        show_result=None if args.no_show else "Camera Viewer",
        image_processing_callback=on_frame,
        poll_interval=0.0003,
    )
    handler.run()
    log.info("Started %s camera", args.camera_type)
    try:
        nectar.spin()
    finally:
        handler.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
