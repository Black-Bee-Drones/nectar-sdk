"""CLI for running inference with detection models."""

import argparse
import logging
import sys
from pathlib import Path

import cv2

try:
    import supervision as sv
except ImportError:
    sv = None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run inference with detection models")

    parser.add_argument("--model", type=str, required=True, help="Model path or name")
    parser.add_argument("--input", type=str, required=True, help="Input image or directory")
    parser.add_argument(
        "--output", type=str, default="outputs/predictions", help="Output directory"
    )
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--conf-threshold", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--iou-threshold", type=float, default=0.45, help="IoU threshold")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    parser.add_argument("--show", action="store_true", help="Display predictions")
    parser.add_argument("--save-txt", action="store_true", help="Save predictions to text")

    return parser.parse_args()


def process_image(
    detector,
    image_path: str,
    conf_threshold: float,
    iou_threshold: float,
    output_dir: Path,
    show: bool = False,
    save_txt: bool = False,
) -> None:
    """Process a single image."""
    logger = logging.getLogger(__name__)

    logger.info("Processing: %s", image_path)

    result = detector.detect(image_path, conf=conf_threshold, iou=iou_threshold)

    image = cv2.imread(image_path)
    image_name = Path(image_path).stem
    output_path = output_dir / f"{image_name}_prediction.jpg"

    output_dir.mkdir(parents=True, exist_ok=True)

    if len(result) > 0:
        # Draw annotations
        annotated = detector.draw_detections(image.copy(), result)
        cv2.imwrite(str(output_path), annotated)
        logger.info("Saved: %s", output_path)

        if show:
            cv2.imshow("Prediction", annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        if save_txt:
            txt_path = output_dir / f"{image_name}_prediction.txt"
            with open(txt_path, "w") as f:
                for det in result.detections:
                    x1, y1, x2, y2 = det.bbox
                    w, h = x2 - x1, y2 - y1
                    x_c, y_c = x1 + w / 2, y1 + h / 2
                    f.write(f"{det.class_id} {x_c} {y_c} {w} {h} {det.confidence}\n")
    else:
        logger.info("No detections in %s", image_path)
        cv2.imwrite(str(output_path), image)

    logger.info("Inference time: %.3fs", result.inference_time)
    logger.info("Detections: %d", len(result))


def process_directory(
    detector,
    image_dir: str,
    conf_threshold: float,
    iou_threshold: float,
    output_dir: Path,
    batch_size: int = 1,
    save_txt: bool = False,
) -> None:
    """Process directory of images."""
    logger = logging.getLogger(__name__)

    extensions = [".jpg", ".jpeg", ".png", ".bmp"]
    image_paths = []

    for ext in extensions:
        image_paths.extend(Path(image_dir).glob(f"*{ext}"))
        image_paths.extend(Path(image_dir).glob(f"*{ext.upper()}"))

    if not image_paths:
        logger.error("No images found in %s", image_dir)
        return

    logger.info("Found %d images", len(image_paths))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process in batches
    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(image_paths) + batch_size - 1) // batch_size
        logger.info("Batch %d/%d", batch_num, total_batches)

        if batch_size == 1:
            # Single image processing
            for img_path in batch_paths:
                process_image(
                    detector,
                    str(img_path),
                    conf_threshold,
                    iou_threshold,
                    output_dir,
                    show=False,
                    save_txt=save_txt,
                )
        else:
            # Batch processing
            results = detector.detect_batch(
                [str(p) for p in batch_paths],
                conf=conf_threshold,
                iou=iou_threshold,
            )

            for img_path, result in zip(batch_paths, results):
                image = cv2.imread(str(img_path))
                image_name = img_path.stem
                output_path = output_dir / f"{image_name}_prediction.jpg"

                if len(result) > 0:
                    annotated = detector.draw_detections(image.copy(), result)
                    cv2.imwrite(str(output_path), annotated)

                    if save_txt:
                        txt_path = output_dir / f"{image_name}_prediction.txt"
                        with open(txt_path, "w") as f:
                            for det in result.detections:
                                x1, y1, x2, y2 = det.bbox
                                w, h = x2 - x1, y2 - y1
                                x_c, y_c = x1 + w / 2, y1 + h / 2
                                f.write(f"{det.class_id} {x_c} {y_c} {w} {h} {det.confidence}\n")
                else:
                    cv2.imwrite(str(output_path), image)

    logger.info("Results saved to %s", output_dir)


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    if sv is None:
        logger.error("supervision is required. Install: pip install supervision")
        sys.exit(1)

    args = parse_args()

    # Use Detector facade for auto-detection
    from nectar.ai.detection import Detector

    logger.info("Loading model: %s", args.model)

    detector = Detector(
        model_source=args.model,
        device=args.device,
        confidence_threshold=args.conf_threshold,
    )
    detector.load()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if input_path.is_file():
        process_image(
            detector,
            str(input_path),
            args.conf_threshold,
            args.iou_threshold,
            output_dir,
            args.show,
            args.save_txt,
        )
    elif input_path.is_dir():
        process_directory(
            detector,
            str(input_path),
            args.conf_threshold,
            args.iou_threshold,
            output_dir,
            args.batch_size,
            args.save_txt,
        )
    else:
        logger.error("Invalid input: %s", args.input)
        sys.exit(1)

    logger.info("Prediction completed")


if __name__ == "__main__":
    main()
