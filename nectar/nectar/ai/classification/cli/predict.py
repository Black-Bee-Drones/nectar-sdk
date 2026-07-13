"""CLI for running inference with classification models."""

import argparse
import json
import logging
import sys
from pathlib import Path

import cv2

from nectar.ai.cli.common import add_common_predict_args


def parse_args():
    parser = argparse.ArgumentParser(description="Run inference with classification models")
    add_common_predict_args(parser)
    parser.add_argument("--topk", type=int, default=5, help="Number of top predictions")
    return parser.parse_args()


def process_image(classifier, image_path: str, topk: int, output_dir: Path, show: bool = False):
    logger = logging.getLogger(__name__)
    logger.info("Processing: %s", image_path)

    result = classifier.classify(image_path, topk=topk)
    image = cv2.imread(image_path)
    image_name = Path(image_path).stem
    output_dir.mkdir(parents=True, exist_ok=True)

    annotated = classifier.draw_classification(image.copy(), result, topk=topk)
    out_img = output_dir / f"{image_name}_classification.jpg"
    cv2.imwrite(str(out_img), annotated)

    out_json = output_dir / f"{image_name}_classification.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    logger.info("Top-1: %s (%.3f)", result.top1_name, result.top1_confidence or 0.0)
    logger.info("Saved: %s", out_img)

    if show:
        cv2.imshow("Classification", annotated)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def process_directory(classifier, image_dir: str, topk: int, output_dir: Path, batch_size: int = 1):
    logger = logging.getLogger(__name__)
    extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
    image_paths = []
    for ext in extensions:
        image_paths.extend(Path(image_dir).glob(f"*{ext}"))
        image_paths.extend(Path(image_dir).glob(f"*{ext.upper()}"))

    if not image_paths:
        logger.error("No images found in %s", image_dir)
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [str(p) for p in sorted(image_paths)]
    batch_size = max(1, int(batch_size or 1))

    if batch_size == 1:
        for img_path in paths:
            process_image(classifier, img_path, topk, output_dir, show=False)
        return

    for start in range(0, len(paths), batch_size):
        batch = paths[start : start + batch_size]
        results = classifier.classify_batch(batch, topk=topk)
        for img_path, result in zip(batch, results):
            image = cv2.imread(img_path)
            image_name = Path(img_path).stem
            annotated = classifier.draw_classification(image.copy(), result, topk=topk)
            out_img = output_dir / f"{image_name}_classification.jpg"
            cv2.imwrite(str(out_img), annotated)
            out_json = output_dir / f"{image_name}_classification.json"
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            logger.info("Top-1: %s (%.3f)", result.top1_name, result.top1_confidence or 0.0)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    args = parse_args()

    from nectar.ai.classification import Classifier

    logger.info("Loading model: %s", args.model)
    classifier = Classifier(model_source=args.model, device=args.device, topk=args.topk)
    classifier.load()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if input_path.is_file():
        process_image(classifier, str(input_path), args.topk, output_dir, args.show)
    elif input_path.is_dir():
        process_directory(classifier, str(input_path), args.topk, output_dir, args.batch_size)
    else:
        logger.error("Invalid input: %s", args.input)
        sys.exit(1)

    logger.info("Prediction completed")


if __name__ == "__main__":
    main()
