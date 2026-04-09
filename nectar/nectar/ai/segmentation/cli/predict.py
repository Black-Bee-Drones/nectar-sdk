"""CLI for running inference with segmentation models."""

import argparse
import logging
import sys
from pathlib import Path

import cv2

try:
    import supervision as sv
except ImportError:
    sv = None

from nectar.ai.cli.common import add_common_predict_args


def parse_args():
    """Parse command line arguments for segmentation prediction."""
    parser = argparse.ArgumentParser(description="Run inference with segmentation models")
    add_common_predict_args(parser)
    parser.add_argument("--save-masks", action="store_true", help="Save individual mask PNGs")
    return parser.parse_args()


def process_image(
    segmentor,
    image_path: str,
    conf_threshold: float,
    iou_threshold: float,
    output_dir: Path,
    show: bool = False,
    save_masks: bool = False,
) -> None:
    """Process a single image."""
    logger = logging.getLogger(__name__)

    logger.info("Processing: %s", image_path)

    result = segmentor.segment(image_path, conf=conf_threshold, iou=iou_threshold)

    image = cv2.imread(image_path)
    image_name = Path(image_path).stem
    output_path = output_dir / f"{image_name}_segmentation.jpg"

    output_dir.mkdir(parents=True, exist_ok=True)

    if len(result) > 0:
        annotated = segmentor.draw_segmentations(image.copy(), result)
        cv2.imwrite(str(output_path), annotated)
        logger.info("Saved: %s", output_path)

        if show:
            cv2.imshow("Segmentation", annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        if save_masks:
            masks_dir = output_dir / f"{image_name}_masks"
            masks_dir.mkdir(parents=True, exist_ok=True)
            for idx, seg in enumerate(result.segmentations):
                if seg.mask is not None:
                    mask_path = masks_dir / f"mask_{idx}_{seg.class_name}_{seg.confidence:.2f}.png"
                    mask_img = (seg.mask > 0).astype("uint8") * 255
                    cv2.imwrite(str(mask_path), mask_img)
    else:
        logger.info("No segmentations in %s", image_path)
        cv2.imwrite(str(output_path), image)

    logger.info("Inference time: %.3fs", result.inference_time)
    logger.info("Segmentations: %d", len(result))


def process_directory(
    segmentor,
    image_dir: str,
    conf_threshold: float,
    iou_threshold: float,
    output_dir: Path,
    batch_size: int = 1,
    save_masks: bool = False,
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

    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(image_paths) + batch_size - 1) // batch_size
        logger.info("Batch %d/%d", batch_num, total_batches)

        for img_path in batch_paths:
            process_image(
                segmentor, str(img_path), conf_threshold, iou_threshold,
                output_dir, show=False, save_masks=save_masks,
            )

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

    from nectar.ai.segmentation import Segmentor

    logger.info("Loading model: %s", args.model)

    segmentor = Segmentor(
        model_source=args.model,
        device=args.device,
        confidence_threshold=args.conf_threshold,
    )
    segmentor.load()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if input_path.is_file():
        process_image(
            segmentor, str(input_path), args.conf_threshold, args.iou_threshold,
            output_dir, args.show, args.save_masks,
        )
    elif input_path.is_dir():
        process_directory(
            segmentor, str(input_path), args.conf_threshold, args.iou_threshold,
            output_dir, args.batch_size, args.save_masks,
        )
    else:
        logger.error("Invalid input: %s", args.input)
        sys.exit(1)

    logger.info("Prediction completed")


if __name__ == "__main__":
    main()
