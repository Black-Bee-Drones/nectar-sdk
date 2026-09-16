#!/usr/bin/env python3
"""Capture and save frames from any supported camera.

Examples::

    python collect_photos.py --source webcam --capture-interval 0.5
    python collect_photos.py --source realsense --jpeg-quality 95 --show
    python collect_photos.py --source webcam --publish --publish-scale 0.3
"""

import argparse
import logging
import os
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2

import nectar
from nectar.vision.camera import ImageHandler, add_camera_arguments, parse_camera_args
from nectar.vision.stream import CompressedFramePublisher, add_stream_arguments

log = logging.getLogger("collect_photos")


def _setup_output_dir(output_dir: str, run_name: str) -> Path:
    run_name = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path.home() / output_dir / run_name
    path.mkdir(parents=True, exist_ok=True)
    return path


class Collector:
    def __init__(self, args: argparse.Namespace, source: str, config) -> None:
        self._args = args
        self._output_path = _setup_output_dir(args.output_dir, args.run_name)
        self._count = 0
        self._last_capture = 0.0
        self._stopping = False
        self._publisher: Optional[CompressedFramePublisher] = None
        if args.publish:
            self._publisher = CompressedFramePublisher(
                args.publish_topic, jpeg_quality=args.jpeg_quality
            )

        self.handler = ImageHandler(
            image_source=source,
            config=config,
            show_result="Collect Photos" if args.show else None,
            image_processing_callback=self._on_frame,
            poll_interval=0.01,
        )
        self.handler.run()
        log.info("Saving to %s (interval=%ss)", self._output_path, args.capture_interval)

    def _on_frame(self, frame) -> None:
        if frame is None or self._stopping:
            return
        now = time.time()
        if now - self._last_capture < self._args.capture_interval:
            return
        self._count += 1
        self._last_capture = now

        ext = self._args.image_format
        filepath = self._output_path / f"frame_{self._count:05d}.{ext}"
        params = []
        if ext in ("jpg", "jpeg"):
            params = [cv2.IMWRITE_JPEG_QUALITY, self._args.jpeg_quality]
        elif ext == "png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        cv2.imwrite(str(filepath), frame, params)
        log.info(
            "[%d] Saved %s (%dx%d)",
            self._count,
            filepath.name,
            frame.shape[1],
            frame.shape[0],
        )

        if self._publisher is not None:
            publish_frame = frame
            scale = self._args.publish_scale
            if scale < 1.0:
                publish_frame = cv2.resize(
                    frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                )
            self._publisher.publish(publish_frame)

        if self._args.max_photos > 0 and self._count >= self._args.max_photos:
            log.info("Reached max_photos (%d). Stopping.", self._args.max_photos)
            self._stopping = True
            os.kill(os.getpid(), signal.SIGINT)

    def cleanup(self) -> None:
        self.handler.cleanup()
        if self._publisher is not None:
            self._publisher.cleanup()
        log.info(
            "Collection finished -- %d photos saved to %s",
            self._count,
            self._output_path,
        )


def parse_args():
    p = argparse.ArgumentParser(description="Capture and save camera frames")
    add_camera_arguments(p)
    add_stream_arguments(p, show_default=False, publish_topic="collect_photos/compressed")
    p.add_argument("--output-dir", default="collected_photos")
    p.add_argument("--run-name", default="")
    p.add_argument("--capture-interval", type=float, default=1.0)
    p.add_argument("--image-format", default="jpg")
    p.add_argument("--max-photos", type=int, default=0)
    p.add_argument("--publish-scale", type=float, default=0.5)
    return parse_camera_args(p)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    args, _, source, config = parse_args()
    nectar.init()
    collector = Collector(args, source, config)
    try:
        nectar.spin()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        collector.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
