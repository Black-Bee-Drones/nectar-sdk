#!/usr/bin/env python3
import argparse
import logging

import nectar
from nectar.vision.camera import ImageHandler, add_camera_arguments, parse_camera_args
from nectar.vision.stream import add_stream_arguments

log = logging.getLogger("camera_example")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Camera example using ImageHandler")
    add_camera_arguments(parser)
    add_stream_arguments(parser, show_default=True, include_publish=False)
    args, _, source, config = parse_camera_args(parser)
    count = [0]

    def on_frame(frame) -> None:
        if frame is None:
            return
        count[0] += 1
        log.info("Received frame %d with shape: %s", count[0], frame.shape)

    nectar.init()
    handler = ImageHandler(
        image_source=source,
        config=config,
        show_result="Camera Viewer" if args.show else None,
        image_processing_callback=on_frame,
    )
    handler.run()
    log.info("Started %s camera", source)
    try:
        nectar.spin()
    finally:
        handler.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
