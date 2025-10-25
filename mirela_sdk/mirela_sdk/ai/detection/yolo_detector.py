import cv2
import numpy as np
from typing import Optional
from pathlib import Path

from .base import UltralyticsDetectionModel, DetectionResult
from .models.model_loader import ModelLoader


class YOLODetector:

    def __init__(
        self,
        model_source: str,
        confidence_threshold: float = 0.25,
        image_size: int = 640,
        device: str = "auto",
        auto_load: bool = True,
        token: Optional[str] = None,
    ):
        """
        Initialize YOLO detector.

        Args:
            model_source: Local path or HuggingFace repo (e.g., "user/repo:model.pt")
            confidence_threshold: Minimum confidence for detections
            image_size: Input image size for inference
            device: Device to run on ('auto', 'cpu', 'cuda', '0', '1', etc.)
                   'auto' will automatically detect and use GPU if available
            auto_load: Automatically load model on initialization
            token: HuggingFace API token for private repos (or set HF_TOKEN env var)

        Example:
            # From local file (auto-detect GPU)
            detector = YOLODetector("/path/to/model.pt")

            # Force CPU usage
            detector = YOLODetector("/path/to/model.pt", device="cpu")

            # From public Hugging Face repo
            detector = YOLODetector("blackbeedrones/cbr-25-base:yolov11n.pt")

            # From private Hugging Face repo
            detector = YOLODetector("blackbeedrones/cbr-25-base:yolov11n.pt", token="hf_...")
        """
        self.model_source = model_source
        self.confidence_threshold = confidence_threshold
        self.image_size = image_size
        self.device = device

        self.model_path = ModelLoader.load(model_source, token=token)

        self.model = UltralyticsDetectionModel(
            model_path=self.model_path,
            confidence_threshold=confidence_threshold,
            image_size=image_size,
            device=device,
        )

        if auto_load:
            self.load()

    def load(self) -> bool:
        """Load the YOLO model."""
        return self.model.load()

    def detect(
        self,
        image: np.ndarray,
        conf: Optional[float] = None,
    ) -> DetectionResult:
        """
        Run detection on image.

        Args:
            image: Input image (BGR format)
            conf: Override confidence threshold

        Returns:
            DetectionResult with all detections
        """
        return self.model.predict(image, conf=conf)

    def draw_detections(
        self,
        image: np.ndarray,
        result: DetectionResult,
        show_labels: bool = True,
        show_confidence: bool = True,
        show_class: bool = True,
        annotator_type: str = "box",
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
        return self.model.draw_detections(
            image,
            result,
            show_labels,
            show_confidence,
            show_class,
            annotator_type,
            thickness,
            text_scale,
        )

    def save_detection_image(
        self,
        image: np.ndarray,
        result: DetectionResult,
        save_path: str,
        draw_options: Optional[dict] = None,
    ) -> str:
        """
        Save image with detection annotations.

        Args:
            image: Input image
            result: DetectionResult to draw
            save_path: Output file path
            draw_options: Optional dict with drawing parameters

        Returns:
            Path to saved image
        """
        draw_options = draw_options or {}
        annotated = self.draw_detections(image, result, **draw_options)

        # Create directory if needed
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        cv2.imwrite(save_path, annotated)
        return save_path

    @property
    def class_names(self) -> dict:
        """Get class names from model."""
        return self.model.class_names

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model.model is not None
