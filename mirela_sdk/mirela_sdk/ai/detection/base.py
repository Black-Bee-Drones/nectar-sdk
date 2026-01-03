from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np

from mirela_sdk.vision.types import BoundingBox, Point2D

try:
    import torch
except ImportError:
    torch = None

try:
    import supervision as sv
except ImportError:
    sv = None


@dataclass
class Detection:
    bbox: List[int]
    confidence: float
    class_id: int
    class_name: str = ""

    @property
    def center(self) -> Point2D:
        x1, y1, x2, y2 = self.bbox
        return Point2D(x=(x1 + x2) / 2, y=(y1 + y2) / 2)

    @property
    def bounding_box(self) -> BoundingBox:
        x1, y1, x2, y2 = self.bbox
        return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


@dataclass
class DetectionResult:
    """Container for detection results."""

    detections: List[Detection]
    image: Optional[np.ndarray] = None
    inference_time: float = 0.0

    def __len__(self) -> int:
        return len(self.detections)

    def __getitem__(self, idx: int) -> Detection:
        return self.detections[idx]


class BaseDetectionModel(ABC):
    """Abstract base class for detection models."""

    def __init__(self, model_path: str, confidence_threshold: float = 0.25):
        """
        Initialize detection model.

        Args:
            model_path: Path to model file
            confidence_threshold: Minimum confidence for detections
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.class_names: Dict[int, str] = {}

    @abstractmethod
    def load(self) -> bool:
        """Load the model. Returns True if successful."""
        raise NotImplementedError

    @abstractmethod
    def predict(self, image: np.ndarray, **kwargs) -> DetectionResult:
        """
        Run inference on image.

        Args:
            image: Input image (BGR format)
            **kwargs: Additional model-specific parameters

        Returns:
            DetectionResult containing all detections
        """
        raise NotImplementedError

    def draw_detections(
        self,
        image: np.ndarray,
        result: DetectionResult,
        show_labels: bool = True,
        show_confidence: bool = True,
        show_class: bool = True,
        annotator_type: str = "box",  # "box", "round_box", "color"
        thickness: int = 2,
        text_scale: float = 0.5,
    ) -> np.ndarray:
        """
        Draw detection annotations using Supervision library.

        Args:
            image: Input image
            result: DetectionResult to draw
            show_labels: Whether to show any labels
            show_confidence: Whether to show confidence scores in labels
            show_class: Whether to show class names in labels
            annotator_type: Type of annotator ("box", "round_box", "color")
            thickness: Line thickness for box annotations
            text_scale: Scale for label text

        Returns:
            Annotated image
        """
        if sv is None:
            raise ImportError(
                "Supervision not installed. Install with: pip install supervision"
            )

        if not result.detections:
            return image.copy()

        xyxy = np.array([det.bbox for det in result.detections])
        confidence = np.array([det.confidence for det in result.detections])
        class_id = np.array([det.class_id for det in result.detections])

        detections = sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
        )

        detections.data["class_name"] = [det.class_name for det in result.detections]

        annotated = image.copy()

        if annotator_type == "round_box":
            box_annotator = sv.RoundBoxAnnotator(
                thickness=thickness,
                color=sv.ColorPalette.DEFAULT,
            )
        elif annotator_type == "color":
            box_annotator = sv.ColorAnnotator(
                color=sv.ColorPalette.DEFAULT,
                opacity=0.3,
            )
        else:
            box_annotator = sv.BoxAnnotator(
                thickness=thickness,
                color=sv.ColorPalette.DEFAULT,
            )

        annotated = box_annotator.annotate(scene=annotated, detections=detections)

        if show_labels:
            labels = []
            for det in result.detections:
                label_parts = []

                if show_class and det.class_name:
                    label_parts.append(det.class_name)
                if show_confidence:
                    label_parts.append(f"{det.confidence:.2f}")

                labels.append(" ".join(label_parts) if label_parts else "")

            if any(labels):
                label_annotator = sv.LabelAnnotator(
                    text_scale=text_scale,
                    text_thickness=max(1, int(thickness * 0.5)),
                )
                annotated = label_annotator.annotate(
                    scene=annotated, detections=detections, labels=labels
                )

        return annotated


class UltralyticsDetectionModel(BaseDetectionModel):
    """Ultralytics YOLO detection model wrapper."""

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.25,
        image_size: int = 640,
        device: str = "auto",
    ):
        """
        Initialize Ultralytics model.

        Args:
            model_path: Path to YOLO model (.pt, .onnx, .engine)
            confidence_threshold: Minimum confidence for detections
            image_size: Input image size for inference
            device: Device to run on ('auto', 'cpu', 'cuda', '0', '1', etc.)
                   'auto' will automatically detect and use GPU if available
        """
        super().__init__(model_path, confidence_threshold)
        self.image_size = image_size
        self.device = self._resolve_device(device)

    def _resolve_device(self, device: str) -> str:
        """
        Resolve device string to actual device.

        Args:
            device: Device string ('auto', 'cpu', 'cuda', '0', '1', etc.)

        Returns:
            Resolved device string that YOLO can use
        """
        if device == "auto":
            if torch is not None and torch.cuda.is_available():
                return "cuda"
            else:
                return "cpu"

        if device.startswith("cuda") or device.isdigit():
            if torch is not None and torch.cuda.is_available():
                try:
                    if device.isdigit():
                        device_id = int(device)
                        if device_id < torch.cuda.device_count():
                            return str(device_id)
                        else:
                            print(f"GPU {device_id} not available, using cuda:0")
                            return "0"
                    return device
                except:
                    print(f"Failed to use device {device}, falling back to auto-detect")
                    return "cuda" if torch.cuda.is_available() else "cpu"
            else:
                print(f"CUDA not available, falling back to CPU")
                return "cpu"

        return device

    def load(self) -> bool:
        """Load Ultralytics model."""
        try:
            from ultralytics import YOLO
            from ultralytics.utils import LOGGER

            LOGGER.setLevel("ERROR")

            self.model = YOLO(self.model_path, task="detect")
            self.model.to(self.device)
            # Move model to specified device
            if hasattr(self.model, "names"):
                self.class_names = self.model.names

            actual_device = (
                next(self.model.model.parameters()).device
                if hasattr(self.model.model, "parameters")
                else self.device
            )
            print(f"Model loaded on device: {actual_device}")
            if torch is not None and torch.cuda.is_available():
                print(f"CUDA available: {torch.cuda.get_device_name(0)}")

            return True

        except ImportError as exc:
            raise ImportError(
                "Ultralytics not installed. Install with: pip install ultralytics"
            ) from exc
        except Exception as exc:
            print(f"Failed to load model: {exc}")
            return False

    def predict(
        self,
        image: np.ndarray,
        conf: Optional[float] = None,
        imgsz: Optional[int] = None,
        **kwargs,
    ) -> DetectionResult:
        """
        Run YOLO inference.

        Args:
            image: Input image (BGR format)
            conf: Override confidence threshold
            imgsz: Override image size
            **kwargs: Additional YOLO parameters

        Returns:
            DetectionResult with all detections
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        import time

        conf = conf or self.confidence_threshold
        imgsz = imgsz or self.image_size

        start_time = time.time()

        results = self.model(
            image, conf=conf, imgsz=imgsz, device=self.device, verbose=False, **kwargs
        )

        inference_time = time.time() - start_time

        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = self.class_names.get(class_id, str(class_id))

                    detection = Detection(
                        bbox=[int(x1), int(y1), int(x2), int(y2)],
                        confidence=confidence,
                        class_id=class_id,
                        class_name=class_name,
                    )
                    detections.append(detection)

        return DetectionResult(
            detections=detections,
            image=image,
            inference_time=inference_time,
        )
