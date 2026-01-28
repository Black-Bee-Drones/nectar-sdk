#!/usr/bin/env python3
"""
Process a directory of images:

    python batch_detector.py --input /path/to/images --output-dir results/

Process a video file:

    python batch_detector.py --input video.mp4 --output-dir results/

Use a specific model and framework:

    python batch_detector.py --input images/ --output-dir results/ \
        --model-source yolov8n.pt --framework ultralytics

Use Transformers DETR:

    python batch_detector.py --input images/ --output-dir results/ \
        --model-source facebook/detr-resnet-50 --framework transformers
"""

import argparse
from pathlib import Path
from typing import List, Tuple
import tempfile

import cv2
import numpy as np

from mirela_sdk.ai.detection import Detector, Framework


def extract_video_frames(
    video_path: str, output_dir: str = None
) -> Tuple[List[str], float]:
    """
    Extract frames from video file.

    Parameters
    ----------
    video_path : str
        Path to video file.
    output_dir : str, optional
        Directory to save frames.

    Returns
    -------
    Tuple[List[str], float]
        Tuple of (frame_files, original_fps).
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
    """
    Get sorted list of image files from directory.

    Parameters
    ----------
    directory : str
        Path to directory.

    Returns
    -------
    List[str]
        Sorted list of image file paths.
    """
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_files = []

    for file in sorted(Path(directory).iterdir()):
        if file.suffix.lower() in valid_extensions:
            image_files.append(str(file))

    return image_files


def process_images(
    image_files: List[str],
    detector: Detector,
    output_dir: str,
    annotator_type: str = "box",
    show_labels: bool = True,
    show_confidence: bool = True,
    fps: float = 30,
) -> None:
    """
    Process images with detection and save results.

    Parameters
    ----------
    image_files : List[str]
        List of image file paths.
    detector : Detector
        Initialized detector instance.
    output_dir : str
        Output directory.
    annotator_type : str, optional
        Annotation style. Defaults to "box".
    show_labels : bool, optional
        Show detection labels. Defaults to True.
    show_confidence : bool, optional
        Show confidence scores. Defaults to True.
    fps : float, optional
        FPS for output video. Defaults to 30.
    """
    frames_dir = Path(output_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    first_img = cv2.imread(image_files[0])
    height, width = first_img.shape[:2]

    # Create video writer
    video_path = Path(output_dir) / "detection_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))

    print(f"Processing {len(image_files)} images...")
    print(f"Framework: {detector.framework.value}")
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

        # Run detection
        result = detector.detect(frame)
        num_detections = len(result)
        total_detections += num_detections
        total_inference_time += result.inference_time

        # Draw annotations
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

        # Add frame info overlay
        add_frame_info(
            annotated,
            idx + 1,
            len(image_files),
            num_detections,
            result.inference_time,
            detector.framework.value,
        )

        # Save frame
        frame_filename = frames_dir / f"frame_{idx:04d}.jpg"
        cv2.imwrite(str(frame_filename), annotated)

        # Write to video
        video_writer.write(annotated)

        # Progress update
        if (idx + 1) % 10 == 0 or idx == len(image_files) - 1:
            print(
                f"Processed {idx + 1}/{len(image_files)} frames | "
                f"Current: {num_detections} detections | "
                f"Inference: {result.inference_time*1000:.1f}ms"
            )

    video_writer.release()

    # Summary
    print("-" * 60)
    print("Processing complete!")
    print(f"Framework: {detector.framework.value}")
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
    framework: str,
) -> None:
    """
    Add frame information overlay.

    Parameters
    ----------
    frame : np.ndarray
        Image to annotate.
    frame_num : int
        Current frame number.
    total_frames : int
        Total number of frames.
    detections : int
        Number of detections.
    inference_time : float
        Inference time in seconds.
    framework : str
        Framework name.
    """
    fps = 1.0 / inference_time if inference_time > 0 else 0

    overlay_lines = [
        f"Framework: {framework}",
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
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch detection on image sequences or video files"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input path (directory with images or video file)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Directory to save output frames and video",
    )
    parser.add_argument(
        "--model-source",
        type=str,
        default="yolov8n.pt",
        help="Model source (local path or HuggingFace repo:file)",
    )
    parser.add_argument(
        "--framework",
        type=str,
        default="",
        choices=["", "ultralytics", "transformers", "rfdetr"],
        help="Framework to use (empty for auto-detect)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
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
        "--hide-labels", action="store_true", help="Hide detection labels"
    )
    parser.add_argument(
        "--hide-confidence", action="store_true", help="Hide confidence scores"
    )
    parser.add_argument("--fps", type=int, default=30, help="FPS for output video")

    args = parser.parse_args()

    # Determine input type
    input_path = Path(args.input)
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    video_fps = None

    if input_path.is_file() and input_path.suffix.lower() in video_extensions:
        print(f"Processing video file: {args.input}")
        frames_dir = Path(args.output_dir) / "extracted_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        image_files, video_fps = extract_video_frames(args.input, str(frames_dir))
        output_fps = video_fps
        print(f"Using original video FPS: {output_fps:.2f}")
    elif input_path.is_dir():
        image_files = get_image_files(args.input)
        if not image_files:
            print(f"No image files found in {args.input}")
            return
        print(f"Found {len(image_files)} images in {args.input}")
        output_fps = args.fps
    else:
        print(f"Error: '{args.input}' is not a valid video file or directory")
        return

    # Resolve framework
    framework = None
    if args.framework:
        try:
            framework = Framework(args.framework.lower())
            print(f"Using explicit framework: {framework.value}")
        except ValueError:
            print(f"Unknown framework: {args.framework}, using auto-detect")

    # Initialize detector
    print(f"Loading model: {args.model_source}")
    print(f"Device preference: {args.device}")

    detector = Detector(
        model_source=args.model_source,
        framework=framework,
        device=args.device,
        confidence_threshold=args.confidence,
    )
    detector.load()

    print(f"Model loaded! Framework: {detector.framework.value}")

    # Log class names
    if detector.class_names:
        num_classes = len(detector.class_names)
        print(f"Model has {num_classes} classes")
        if num_classes <= 10:
            for idx, name in detector.class_names.items():
                print(f"  Class {idx}: {name}")

    # Process images
    process_images(
        image_files=image_files,
        detector=detector,
        output_dir=args.output_dir,
        annotator_type=args.annotator_type,
        show_labels=not args.hide_labels,
        show_confidence=not args.hide_confidence,
        fps=output_fps,
    )


if __name__ == "__main__":
    main()
