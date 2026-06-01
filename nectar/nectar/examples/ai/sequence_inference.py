#!/usr/bin/env python3
"""
Run one or more detection / segmentation models over a sequence of images
(or a video file) and write a per-model annotated MP4 + per-frame JPGs.

The input frames are processed in natural-sort order so an image directory
behaves like a video.  Detection models render bounding boxes; segmentation
models render coloured masks (and optionally the box outline).  The model
type (Detector vs Segmentor) is auto-detected from the model name suffix
(``-seg`` / ``_seg``) but can be forced per-model via ``model:type`` syntax.

Examples
--------
Run all three SAE-2026 hook models on a downloaded session directory::

    python3 sequence_inference.py \\
        --input nectar/nectar/ai/data/sae-2026-hook/roboflow/session_2026-04-16_132147_1534imgs_frame \\
        --output-dir nectar/nectar/ai/outputs/sae-2026-hook/inference/session_2026-04-16_132147 \\
        --models \\
            blackbeedrones/sae-2026-hook-sphere-yolo26n:weights/best.pt \\
            blackbeedrones/sae-2026-hook-rope-yolo26n-seg:weights/best.pt \\
            blackbeedrones/sae-2026-hook-all-yolo26n-seg:weights/best.pt

Run on a cell-phone clip::

    python3 sequence_inference.py \\
        --input "nectar/nectar/ai/data/cell/WhatsApp Video 2026-05-04 at 00.09.49.mp4" \\
        --output-dir nectar/nectar/ai/outputs/sae-2026-hook/inference/cell_0949 \\
        --models \\
            blackbeedrones/sae-2026-hook-sphere-yolo26n:weights/best.pt \\
            blackbeedrones/sae-2026-hook-all-yolo26n-seg:weights/best.pt

Force a model type explicitly (model_source@type)::

    --models my/repo:foo.pt@detection  bar/baz:seg.pt@segmentation
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

logger = logging.getLogger("sequence_inference")

# High-contrast palettes tuned for warm-coloured targets (orange sphere,
# red/orange rope). Values are RGB.
_PALETTES = {
    # Cyan, magenta, lime — strong complements of orange / red.
    "contrast": [(0, 255, 255), (255, 0, 255), (0, 255, 0)],
    # Brighter / more saturated set if "contrast" still blends in.
    "vivid": [(0, 255, 255), (255, 0, 200), (170, 255, 0), (0, 200, 255)],
    # Falls back to supervision's default rainbow palette.
    "default": None,
}

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

_NAT_RE = re.compile(r"(\d+)")


def _natural_key(name: str):
    return [int(p) if p.isdigit() else p.lower() for p in _NAT_RE.split(name)]


# --- Model spec -----------------------------------------------------------


@dataclass
class ModelSpec:
    """Parsed model specifier from CLI."""

    source: str  # e.g. ``blackbeedrones/sae-2026-hook-sphere-yolo26n:weights/best.pt``
    task: str  # ``detection`` | ``segmentation``
    name: str  # short label used for output dir / overlay

    @classmethod
    def parse(cls, raw: str) -> "ModelSpec":
        # Allow ``source@task`` to override auto-detection.
        if "@" in raw:
            source, task = raw.rsplit("@", 1)
            task = task.lower()
            if task not in {"detection", "det", "segmentation", "seg"}:
                raise ValueError(f"Unknown task '{task}' in '{raw}'")
            task = "segmentation" if task.startswith("seg") else "detection"
        else:
            source = raw
            task = cls._auto_task(source)

        name = cls._short_name(source)
        return cls(source=source, task=task, name=name)

    @staticmethod
    def _auto_task(source: str) -> str:
        s = source.lower()
        if "-seg" in s or "_seg" in s or "/seg" in s or s.endswith("seg"):
            return "segmentation"
        return "detection"

    @staticmethod
    def _short_name(source: str) -> str:
        # Strip the file path portion of HF specs like ``user/repo:weights/best.pt``
        head = source.split(":", 1)[0]
        # And keep just the model repo / file stem
        base = head.split("/")[-1]
        # If it's a local path, use stem
        if os.path.exists(source):
            base = Path(source).stem
        return re.sub(r"[^A-Za-z0-9_.-]", "_", base)


# --- Frame source ---------------------------------------------------------


def collect_frames(input_path: Path, tmp_dir: Path) -> Tuple[List[Path], float]:
    """Return ``(frame_paths, fps)`` for either an image dir or a video file."""
    if input_path.is_dir():
        frames = sorted(
            (p for p in input_path.iterdir() if p.suffix.lower() in IMAGE_EXTS),
            key=lambda p: _natural_key(p.name),
        )
        if not frames:
            raise ValueError(f"No images found in {input_path}")
        return frames, 0.0  # caller will fall back to args.fps

    if input_path.is_file() and input_path.suffix.lower() in VIDEO_EXTS:
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {input_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info("Video %s: %d frames @ %.2f fps", input_path.name, total, fps)
        out: List[Path] = []
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            dst = tmp_dir / f"frame_{idx:06d}.jpg"
            cv2.imwrite(str(dst), frame)
            out.append(dst)
            idx += 1
            if idx % 200 == 0:
                logger.info("  extracted %d/%d", idx, total)
        cap.release()
        return out, fps

    raise ValueError(f"--input must be a directory of images or a video file: {input_path}")


# --- Annotation (high-contrast) -------------------------------------------


@dataclass
class AnnotConfig:
    """How to render predictions on top of frames."""

    palette: List[Tuple[int, int, int]]  # list of (R, G, B); None falls back to sv default
    box_thickness: int = 3
    text_scale: float = 0.55
    mask_opacity: float = 0.35
    mask_outline: bool = True
    mask_outline_thickness: int = 3


def _hex_to_rgb(s: str) -> Tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Bad hex color: {s!r} (use RRGGBB)")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _parse_class_conf(raw: Optional[str]) -> Dict[str, float]:
    """Parse 'name=val,name=val' into a dict (case-insensitive on names)."""
    if not raw:
        return {}
    out: Dict[str, float] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"Bad --class-conf entry: {chunk!r} (expected name=value)")
        name, val = chunk.split("=", 1)
        out[name.strip().lower()] = float(val.strip())
    return out


def _filter_by_class_conf(items, class_conf: Dict[str, float], floor: float):
    """Keep items whose confidence >= the per-class threshold (or ``floor`` if absent)."""
    if not class_conf:
        return items
    keep = []
    for it in items:
        thr = class_conf.get((it.class_name or "").lower(), floor)
        if it.confidence >= thr:
            keep.append(it)
    return keep


def _make_palette(name: str, colors_csv: Optional[str]):
    """Build a supervision ColorPalette from a name or comma-separated hexes."""
    import supervision as sv  # local import to keep startup cost low

    if colors_csv:
        cols = [_hex_to_rgb(c) for c in colors_csv.split(",") if c.strip()]
    else:
        cols = _PALETTES.get(name)
    if not cols:
        return sv.ColorPalette.DEFAULT
    return sv.ColorPalette([sv.Color(r, g, b) for (r, g, b) in cols])


def _annotate_detection(image: np.ndarray, result, palette, cfg: AnnotConfig) -> np.ndarray:
    """Draw thick coloured boxes + label chips on a detection result."""
    import supervision as sv

    if not result.detections:
        return image.copy()

    detections = result.to_supervision()
    annotated = image.copy()

    box = sv.BoxAnnotator(thickness=cfg.box_thickness, color=palette)
    annotated = box.annotate(scene=annotated, detections=detections)

    labels = [f"{d.class_name} {d.confidence:.2f}".strip() for d in result.detections]
    if any(labels):
        label = sv.LabelAnnotator(
            color=palette,
            text_color=sv.Color.BLACK,
            text_scale=cfg.text_scale,
            text_thickness=max(1, int(cfg.box_thickness * 0.6)),
        )
        annotated = label.annotate(scene=annotated, detections=detections, labels=labels)
    return annotated


def _annotate_segmentation(image: np.ndarray, result, palette, cfg: AnnotConfig) -> np.ndarray:
    """Draw low-opacity mask fill + sharp polygon outline + label chip."""
    import supervision as sv

    if not result.segmentations:
        return image.copy()

    detections = result.to_supervision()
    annotated = image.copy()

    mask = sv.MaskAnnotator(color=palette, opacity=cfg.mask_opacity)
    annotated = mask.annotate(scene=annotated, detections=detections)

    if cfg.mask_outline:
        poly = sv.PolygonAnnotator(color=palette, thickness=cfg.mask_outline_thickness)
        annotated = poly.annotate(scene=annotated, detections=detections)

    labels = [f"{s.class_name} {s.confidence:.2f}".strip() for s in result.segmentations]
    if any(labels):
        label = sv.LabelAnnotator(
            color=palette,
            text_color=sv.Color.BLACK,
            text_scale=cfg.text_scale,
            text_thickness=max(1, int(cfg.box_thickness * 0.6)),
        )
        annotated = label.annotate(scene=annotated, detections=detections, labels=labels)
    return annotated


# --- Inference runners ----------------------------------------------------


def _add_overlay(frame: np.ndarray, lines: Sequence[str]) -> None:
    pad = 6
    for i, line in enumerate(lines):
        y = 22 + i * 22
        (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (5, y - th - pad), (10 + tw, y + pad // 2), (0, 0, 0), -1)
        cv2.putText(
            frame, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1, cv2.LINE_AA
        )


def run_model(
    spec: ModelSpec,
    frames: Sequence[Path],
    fps: float,
    output_root: Path,
    conf: float,
    iou: float,
    device: str,
    save_frames: bool,
    palette,
    annot: AnnotConfig,
    class_conf: Optional[Dict[str, float]] = None,
) -> dict:
    """Process every ``frames`` entry with one model and write output MP4."""
    out_dir = output_root / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    if save_frames:
        frames_dir.mkdir(parents=True, exist_ok=True)

    # Lazy import so each task only loads what it needs
    if spec.task == "segmentation":
        from nectar.ai.segmentation import Segmentor

        model = Segmentor(model_source=spec.source, device=device, confidence_threshold=conf)
    else:
        from nectar.ai.detection import Detector

        model = Detector(model_source=spec.source, device=device, confidence_threshold=conf)

    logger.info("[%s] Loading %s (task=%s)", spec.name, spec.source, spec.task)
    model.load()

    # When per-class thresholds are given, predict at the lowest of them so we
    # don't drop borderline detections that we'd later want for some classes.
    class_conf = class_conf or {}
    predict_conf = min([conf, *class_conf.values()]) if class_conf else conf
    if class_conf:
        logger.info(
            "[%s] class_conf=%s  predict_conf=%.2f  iou=%.2f",
            spec.name,
            class_conf,
            predict_conf,
            iou,
        )

    # Probe frame size from first valid image
    first = cv2.imread(str(frames[0]))
    if first is None:
        raise RuntimeError(f"Could not read {frames[0]}")
    h, w = first.shape[:2]

    video_path = out_dir / f"{spec.name}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

    classes = ", ".join(model.class_names.values()) if model.class_names else "?"
    logger.info("[%s] Classes: %s", spec.name, classes)
    logger.info("[%s] Output: %s (%dx%d @ %.2f fps)", spec.name, video_path, w, h, fps)

    n_total = 0
    t_total = 0.0
    for i, fp in enumerate(frames):
        frame = cv2.imread(str(fp))
        if frame is None:
            logger.warning("[%s] Skip unreadable %s", spec.name, fp)
            continue

        t0 = time.perf_counter()
        if spec.task == "segmentation":
            result = model.segment(frame, conf=predict_conf, iou=iou)
            if class_conf:
                result.segmentations = _filter_by_class_conf(result.segmentations, class_conf, conf)
            annotated = _annotate_segmentation(frame, result, palette, annot)
        else:
            result = model.detect(frame, conf=predict_conf)
            if class_conf:
                result.detections = _filter_by_class_conf(result.detections, class_conf, conf)
            annotated = _annotate_detection(frame, result, palette, annot)
        dt = time.perf_counter() - t0
        t_total += dt
        n_total += len(result)

        infer_fps = 1.0 / dt if dt > 0 else 0.0
        _add_overlay(
            annotated,
            [
                f"{spec.name}  ({spec.task})",
                f"frame {i + 1}/{len(frames)}",
                f"objs {len(result)}   {dt * 1000:5.1f} ms ({infer_fps:.1f} fps)",
            ],
        )

        writer.write(annotated)
        if save_frames:
            cv2.imwrite(str(frames_dir / f"frame_{i:06d}.jpg"), annotated)

        if (i + 1) % 25 == 0 or i == len(frames) - 1:
            logger.info(
                "[%s] %4d/%d frames | objs=%d | %.1f ms/frame",
                spec.name,
                i + 1,
                len(frames),
                n_total,
                (t_total / (i + 1)) * 1000,
            )

    writer.release()
    avg_ms = (t_total / max(len(frames), 1)) * 1000
    logger.info(
        "[%s] DONE  frames=%d  total_objs=%d  avg=%.1f ms/frame  -> %s",
        spec.name,
        len(frames),
        n_total,
        avg_ms,
        video_path,
    )
    return {
        "name": spec.name,
        "task": spec.task,
        "frames": len(frames),
        "objects": n_total,
        "avg_ms": avg_ms,
        "video": str(video_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run multiple detection/segmentation models over an image sequence or video."
    )
    parser.add_argument("--input", required=True, help="Directory of images OR a video file")
    parser.add_argument("--output-dir", required=True, help="Output root directory")
    parser.add_argument(
        "--models",
        required=True,
        nargs="+",
        help="One or more model sources. Suffix '@detection' or '@segmentation' to override auto-task.",
    )
    parser.add_argument(
        "--conf", type=float, default=0.25, help="Default / fallback confidence threshold"
    )
    parser.add_argument(
        "--class-conf",
        default=None,
        help="Per-class confidence overrides, e.g. 'rose=0.47,sphere=0.70'. "
        "Predict is run at min(conf, *class_conf.values()) and the result "
        "is post-filtered per class.",
    )
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold (segmentation NMS)")
    parser.add_argument("--device", default="auto", help="Device: auto|cpu|cuda|0|...")
    parser.add_argument(
        "--fps",
        type=float,
        default=15.0,
        help="Output FPS for image-directory inputs (videos use source FPS)",
    )
    parser.add_argument(
        "--no-save-frames",
        action="store_true",
        help="Skip writing per-frame JPGs (keeps only the MP4)",
    )
    parser.add_argument(
        "--hf-token",
        default=os.environ.get("HF_TOKEN"),
        help="HuggingFace token (or set HF_TOKEN env var)",
    )

    # Annotation styling (high-contrast defaults so warm targets stand out).
    parser.add_argument(
        "--palette",
        choices=list(_PALETTES.keys()),
        default="contrast",
        help="Built-in colour palette (default: contrast = cyan/magenta/lime, "
        "ideal for orange/red targets)",
    )
    parser.add_argument(
        "--colors",
        default=None,
        help="Override palette with comma-separated hex colours, e.g. '00FFFF,FF00FF,00FF00'",
    )
    parser.add_argument(
        "--box-thickness",
        type=int,
        default=3,
        help="Detection box / mask outline thickness (default 3)",
    )
    parser.add_argument(
        "--text-scale", type=float, default=0.55, help="Label text scale (default 0.55)"
    )
    parser.add_argument(
        "--mask-opacity",
        type=float,
        default=0.35,
        help="Segmentation mask fill opacity (default 0.35)",
    )
    parser.add_argument(
        "--no-mask-outline",
        action="store_true",
        help="Disable the polygon outline drawn around each mask",
    )

    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    if args.hf_token:
        os.environ["HF_TOKEN"] = args.hf_token

    specs = [ModelSpec.parse(m) for m in args.models]
    logger.info("Models:")
    for s in specs:
        logger.info("  - %-50s task=%-13s name=%s", s.source, s.task, s.name)

    class_conf = _parse_class_conf(args.class_conf)
    palette = _make_palette(args.palette, args.colors)
    annot = AnnotConfig(
        palette=[],  # not used directly; supervision palette is the source of truth
        box_thickness=args.box_thickness,
        text_scale=args.text_scale,
        mask_opacity=args.mask_opacity,
        mask_outline=not args.no_mask_outline,
        mask_outline_thickness=args.box_thickness,
    )
    logger.info(
        "Palette: %s%s | box_thickness=%d | mask_opacity=%.2f | outline=%s",
        args.palette,
        f" (override {args.colors})" if args.colors else "",
        args.box_thickness,
        args.mask_opacity,
        annot.mask_outline,
    )

    input_path = Path(args.input)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="seq_inf_") as td:
        tmp_dir = Path(td)
        frames, video_fps = collect_frames(input_path, tmp_dir)
        fps = video_fps if video_fps > 0 else args.fps
        logger.info("Frames: %d  output_fps=%.2f", len(frames), fps)

        results = []
        for spec in specs:
            try:
                results.append(
                    run_model(
                        spec=spec,
                        frames=frames,
                        fps=fps,
                        output_root=output_root,
                        conf=args.conf,
                        iou=args.iou,
                        device=args.device,
                        save_frames=not args.no_save_frames,
                        palette=palette,
                        annot=annot,
                        class_conf=class_conf,
                    )
                )
            except Exception as exc:  # keep going on per-model failure
                logger.exception("[%s] FAILED: %s", spec.name, exc)
                results.append({"name": spec.name, "error": str(exc)})

    logger.info("\nSummary:")
    for r in results:
        if "error" in r:
            logger.info("  %-40s  ERROR: %s", r["name"], r["error"])
        else:
            logger.info(
                "  %-40s  %4d frames | objs=%d | avg=%.1f ms | %s",
                r["name"],
                r["frames"],
                r["objects"],
                r["avg_ms"],
                r["video"],
            )

    return 0 if all("error" not in r for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
