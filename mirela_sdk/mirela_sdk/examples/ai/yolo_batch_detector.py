#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import List, Tuple
import tempfile

import cv2
import numpy as np

from mirela_sdk.ai import YOLODetector


def extract_video_frames(
    video_path: str, output_dir: str = None
) -> Tuple[List[str], float]:
    """Extract frames from video file and save to directory.

    Returns:
        Tuple of (frame_files, original_fps)
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="video_frames_")
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print("Extracting frames from video...")
    print(f"Video FPS: {fps:.2f}, Total frames: {total_frames}")

    frame_files = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_path = Path(output_dir) / f"frame_{frame_idx:06d}.jpg"
        cv2.imwrite(str(frame_path), frame)
        frame_files.append(str(frame_path))

        if (frame_idx + 1) % 100 == 0:
            print(f"  Extracted {frame_idx + 1}/{total_frames} frames...")

        frame_idx += 1

    cap.release()
    print(f"Extracted {len(frame_files)} frames to {output_dir}")

    return frame_files, fps


def get_image_files(directory: str) -> List[str]:
    """Get sorted list of image files from directory."""
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_files = []

    for file in sorted(Path(directory).iterdir()):
        if file.suffix.lower() in valid_extensions:
            image_files.append(str(file))

    return image_files


def process_images(
    image_files: List[str],
    detector: YOLODetector,
    output_dir: str,
    annotator_type: str = "box",
    show_labels: bool = True,
    show_confidence: bool = True,
    fps: float = 30,
) -> None:
    """Process images with YOLO detection and save results."""

    frames_dir = Path(output_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    first_img = cv2.imread(image_files[0])
    height, width = first_img.shape[:2]

    video_path = Path(output_dir) / "detection_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

    print(f"Processing {len(image_files)} images...")
    print(f"Output directory: {output_dir}")
    print(f"Video dimensions: {width}x{height} @ {fps:.2f} fps")
    print("-" * 60)

    total_detections = 0
    total_inference_time = 0

    for idx, img_path in enumerate(image_files):
        frame = cv2.imread(img_path)
        if frame is None:
            print(f"Warning: Could not read {img_path}")
            continue

        result = detector.detect(frame)
        num_detections = len(result)
        total_detections += num_detections
        total_inference_time += result.inference_time

        annotated = detector.draw_detections(
            image=frame,
            result=result,
            show_labels=show_labels,
            show_confidence=show_confidence,
            show_class=True,
            annotator_type=annotator_type,
            thickness=2,
            text_scale=0.6,
        )

        add_frame_info(
            annotated, idx + 1, len(image_files), num_detections, result.inference_time
        )

        frame_filename = frames_dir / f"frame_{idx:04d}.jpg"
        cv2.imwrite(str(frame_filename), annotated)

        video_writer.write(annotated)

        # Progress update
        if (idx + 1) % 10 == 0 or idx == len(image_files) - 1:
            print(
                f"Processed {idx + 1}/{len(image_files)} frames | "
                f"Current: {num_detections} detections | "
                f"Inference: {result.inference_time*1000:.1f}ms"
            )

    video_writer.release()

    print("-" * 60)
    print("Processing complete!")
    print(f"Total frames: {len(image_files)}")
    print(f"Total detections: {total_detections}")
    print(f"Average detections per frame: {total_detections/len(image_files):.2f}")
    print(f"Average inference time: {total_inference_time/len(image_files)*1000:.1f}ms")
    print(f"Output video: {video_path}")
    print(f"Output frames: {frames_dir}")


def add_frame_info(
    frame: np.ndarray,
    frame_num: int,
    total_frames: int,
    detections: int,
    inference_time: float,
) -> None:
    """Add frame information overlay."""
    fps = 1.0 / inference_time if inference_time > 0 else 0

    overlay_lines = [
        f"Frame: {frame_num}/{total_frames}",
        f"Detections: {detections}",
        f"FPS: {fps:.1f}",
    ]

    y_offset = 10
    for i, line in enumerate(overlay_lines):
        y_pos = y_offset + (i + 1) * 25

        (text_width, text_height), _ = cv2.getTextSize(
            line, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
        )

        cv2.rectangle(
            frame,
            (5, y_pos - text_height - 5),
            (10 + text_width, y_pos + 5),
            (0, 0, 0),
            -1,
        )

        cv2.putText(
            frame,
            line,
            (10, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Batch YOLO detection on image sequences or video files"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=False,
        help="Input path (directory with images or video file)",
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        required=False,
        help="[Deprecated] Use --input instead",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Directory to save output frames and video",
    )
    parser.add_argument(
        "--model-path", type=str, default=None, help="Path to YOLO model file (.pt)"
    )
    parser.add_argument(
        "--model-source",
        type=str,
        default=None,
        help="Model source (e.g., 'user/repo:model.pt' for HuggingFace)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.9,
        help="Confidence threshold for detections",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Device to run on ('auto', 'cpu', 'cuda', '0', '1', etc.)",
    )
    parser.add_argument(
        "--annotator-type",
        type=str,
        default="box",
        choices=["box", "round_box", "color"],
        help="Type of annotation to draw",
    )
    parser.add_argument(
        "--show-labels", action="store_true", default=True, help="Show detection labels"
    )
    parser.add_argument(
        "--hide-labels", action="store_true", help="Hide detection labels"
    )
    parser.add_argument(
        "--show-confidence",
        action="store_true",
        default=True,
        help="Show confidence scores",
    )
    parser.add_argument(
        "--hide-confidence", action="store_true", help="Hide confidence scores"
    )
    parser.add_argument("--fps", type=int, default=30, help="FPS for output video")
    parser.add_argument(
        "--hf-token", type=str, default="", help="HuggingFace token for private models"
    )

    args = parser.parse_args()

    input_path = args.input or args.image_dir
    if not input_path:
        print("Error: Either --input or --image-dir must be provided")
        parser.print_help()
        return

    if args.model_path:
        model_source = args.model_path
        print(f"Using model from path: {model_source}")
    elif args.model_source:
        model_source = args.model_source
        print(f"Using model source: {model_source}")
    else:
        model_source = "blackbeedrones/cbr-25-base:yolov11n.pt"
        print(f"Using default model: {model_source}")

    show_labels = not args.hide_labels
    show_confidence = not args.hide_confidence

    input_path_obj = Path(input_path)
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    video_fps = None 

    if input_path_obj.is_file() and input_path_obj.suffix.lower() in video_extensions:
        print(f"Processing video file: {input_path}")
        frames_dir = Path(args.output_dir) / "extracted_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        image_files, video_fps = extract_video_frames(input_path, str(frames_dir))
        output_fps = video_fps
        print(f"Using original video FPS: {output_fps:.2f}")
    elif input_path_obj.is_dir():
        image_files = get_image_files(input_path)
        if not image_files:
            print(f"No image files found in {input_path}")
            return
        print(f"Found {len(image_files)} images in {input_path}")
        output_fps = args.fps
    else:
        print(
            f"Error: Input path '{input_path}' is neither a valid video file nor a directory"
        )
        return

    print("Loading YOLO model...")
    print(f"Device preference: {args.device}")

    detector = YOLODetector(
        model_source=model_source,
        confidence_threshold=args.confidence,
        device=args.device,
        token=args.hf_token if args.hf_token else None,
    )

    print("✓ Model loaded successfully!")

    if detector.class_names:
        num_classes = len(detector.class_names)
        print(f"Model has {num_classes} classes")
        if num_classes <= 10:
            for idx, name in detector.class_names.items():
                print(f"  Class {idx}: {name}")

    process_images(
        image_files=image_files,
        detector=detector,
        output_dir=args.output_dir,
        annotator_type=args.annotator_type,
        show_labels=show_labels,
        show_confidence=show_confidence,
        fps=output_fps,  
    )


if __name__ == "__main__":
    main()
