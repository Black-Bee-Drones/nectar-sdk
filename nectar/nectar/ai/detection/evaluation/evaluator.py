"""Object detection evaluator."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import torch
except ImportError:
    torch = None

try:
    import supervision as sv
    from supervision.metrics.f1_score import F1Score
    from supervision.metrics.mean_average_precision import MeanAveragePrecision
    from supervision.metrics.mean_average_recall import MeanAverageRecall
    from supervision.metrics.precision import Precision
    from supervision.metrics.recall import Recall
except ImportError:
    sv = None

from tqdm import tqdm

from nectar.ai.detection.core.configs import EvaluationConfig, EvaluationMetrics
from nectar.ai.detection.core.types import DetectionInput
from nectar.ai.detection.models.dataset import load_detection_dataset

logger = logging.getLogger(__name__)


class ObjectDetectionEvaluator:
    """
    Evaluator for object detection models.

    Calculates metrics including mAP, precision, recall, F1-score
    and generates visualizations.

    Parameters
    ----------
    model : Any
        Detection model implementing predict() method.
    config : EvaluationConfig
        Evaluation configuration.

    Examples
    --------
    >>> from nectar.ai.detection import YOLODetector, EvaluationConfig
    >>> detector = YOLODetector("yolov8n.pt")
    >>> config = EvaluationConfig(
    ...     model_path="best.pt",
    ...     dataset_path="/path/to/dataset",
    ...     split="test",
    ... )
    >>> evaluator = ObjectDetectionEvaluator(detector, config)
    >>> metrics = evaluator.evaluate()
    >>> print(f"mAP@50: {metrics.map50:.4f}")
    """

    def __init__(self, model: Any, config: EvaluationConfig):
        self.model = model
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # Device setup
        if config.device != "auto":
            self.device = config.device
        elif torch and torch.cuda.is_available():
            self.device = "cuda"
        elif torch and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

    def evaluate(self) -> EvaluationMetrics:
        """
        Run evaluation on dataset.

        Returns
        -------
        EvaluationMetrics
            Evaluation results including mAP, precision, recall, F1.
        """
        if sv is None:
            raise ImportError("supervision is required for evaluation")

        # Load dataset
        dataset = load_detection_dataset(
            self.config.dataset_path,
            self.config.dataset_type,
            self.config.split,
        )

        # Collect all data
        all_images = []
        all_paths = []
        all_gts = []

        for path, image, gt in dataset:
            all_paths.append(path)
            all_images.append(image)
            all_gts.append(gt)

        # Limit samples if specified
        if self.config.num_samples and self.config.num_samples < len(all_images):
            all_images = all_images[: self.config.num_samples]
            all_paths = all_paths[: self.config.num_samples]
            all_gts = all_gts[: self.config.num_samples]

        self.logger.info(f"Evaluating on {len(all_images)} images")

        # Run predictions
        all_preds = []
        all_times = []
        results = []

        for i in tqdm(range(0, len(all_images), self.config.batch_size), desc="Evaluating"):
            batch_images = all_images[i : i + self.config.batch_size]
            batch_paths = all_paths[i : i + self.config.batch_size]
            batch_gts = all_gts[i : i + self.config.batch_size]

            detection_input = DetectionInput(
                image=batch_images,
                conf_threshold=self.config.conf_threshold,
                iou_threshold=self.config.iou_threshold,
                device=self.device,
            )

            start_time = time.time()
            prediction = self.model.predict(detection_input)
            batch_time = time.time() - start_time

            batch_preds = prediction.batch_detections or [prediction.detections]
            all_preds.extend(batch_preds)

            for _ in range(len(batch_images)):
                all_times.append(batch_time / len(batch_images))

            # Save results
            for pred, gt, path in zip(batch_preds, batch_gts, batch_paths):
                results.append(
                    {
                        "image_path": str(path),
                        "ground_truth": self._detections_to_dict(gt),
                        "predictions": self._detections_to_dict(pred),
                        "inference_time": batch_time / len(batch_images),
                    }
                )

        # Save raw results
        with open(self.output_dir / "evaluation_results.json", "w") as f:
            json.dump(results, f, indent=2)

        # Calculate metrics
        metrics = self._calculate_metrics(all_preds, all_gts, dataset.classes)

        # Add timing info
        metrics.inference_time_per_image = sum(all_times) / len(all_times) if all_times else 0
        metrics.total_detections = sum(len(p) for p in all_preds)

        # Generate visualizations
        visualizations = self._generate_visualizations(
            all_images, all_preds, all_gts, all_paths, dataset.classes
        )
        metrics.visualizations = visualizations

        # Save metrics summary
        self._save_metrics_summary(metrics)

        return metrics

    def _calculate_metrics(
        self,
        predictions: List["sv.Detections"],
        targets: List["sv.Detections"],
        classes: List[str],
    ) -> EvaluationMetrics:
        """Calculate evaluation metrics using supervision."""
        # mAP
        map_metric = MeanAveragePrecision()
        map_metric.update(predictions=predictions, targets=targets)
        map_result = map_metric.compute()

        # mAR
        mar_metric = MeanAverageRecall()
        mar_metric.update(predictions=predictions, targets=targets)
        mar_result = mar_metric.compute()

        # Precision, Recall, F1
        precision_metric = Precision()
        recall_metric = Recall()
        f1_metric = F1Score()

        precision_metric.update(predictions=predictions, targets=targets)
        recall_metric.update(predictions=predictions, targets=targets)
        f1_metric.update(predictions=predictions, targets=targets)

        precision_result = precision_metric.compute()
        recall_result = recall_metric.compute()
        f1_result = f1_metric.compute()

        # Save per-class metrics
        self._save_per_class_metrics(
            map_result, precision_result, recall_result, f1_result, classes
        )

        return EvaluationMetrics(
            map50=float(map_result.map50),
            map50_95=float(map_result.map50_95),
            mar50=float(mar_result.mAR_at_100),
            mar50_95=float(mar_result.mAR_at_10),
            precision=float(precision_result.precision_at_50),
            recall=float(recall_result.recall_at_50),
            f1_score=float(f1_result.f1_50),
        )

    def _save_per_class_metrics(
        self,
        map_result,
        precision_result,
        recall_result,
        f1_result,
        classes: List[str],
    ) -> None:
        """Save per-class metrics to CSV."""
        try:
            import pandas as pd

            num_classes = len(classes)

            def extract_per_class(arr, num_classes):
                if arr is None or arr.size == 0:
                    return np.zeros(num_classes)
                if arr.ndim == 2:
                    arr = arr[:, 0]
                result = np.zeros(num_classes)
                copy_len = min(len(arr), num_classes)
                result[:copy_len] = arr[:copy_len]
                return result

            ap50 = extract_per_class(map_result.ap_per_class, num_classes)

            if map_result.ap_per_class is not None and map_result.ap_per_class.ndim == 2:
                ap50_95 = np.mean(map_result.ap_per_class, axis=1)
                ap50_95 = np.pad(ap50_95, (0, max(0, num_classes - len(ap50_95))))[:num_classes]
            else:
                ap50_95 = ap50

            precision = extract_per_class(precision_result.precision_per_class, num_classes)
            recall = extract_per_class(recall_result.recall_per_class, num_classes)
            f1 = extract_per_class(f1_result.f1_per_class, num_classes)

            per_class = []
            for i, cls_name in enumerate(classes):
                per_class.append(
                    {
                        "class_id": i,
                        "class_name": cls_name,
                        "ap50": float(ap50[i]),
                        "ap50_95": float(ap50_95[i]),
                        "precision": float(precision[i]),
                        "recall": float(recall[i]),
                        "f1_score": float(f1[i]),
                    }
                )

            df = pd.DataFrame(per_class)
            df.to_csv(self.output_dir / "per_class_metrics.csv", index=False)

            with open(self.output_dir / "per_class_metrics.json", "w") as f:
                json.dump(per_class, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save per-class metrics: {e}")

    def _generate_visualizations(
        self,
        images: List[np.ndarray],
        predictions: List["sv.Detections"],
        targets: List["sv.Detections"],
        paths: List[str],
        classes: List[str],
    ) -> Dict[str, str]:
        """Generate visualization plots."""
        visualizations = {}

        try:
            # Confusion matrix
            cm = sv.ConfusionMatrix.from_detections(
                predictions=predictions,
                targets=targets,
                classes=classes,
                conf_threshold=self.config.conf_threshold,
                iou_threshold=self.config.iou_threshold,
            )
            cm_path = self._plot_confusion_matrix(cm, classes)
            visualizations["confusion_matrix"] = cm_path

        except Exception as e:
            self.logger.error(f"Failed to generate confusion matrix: {e}")

        try:
            # Sample predictions
            samples_path = self._plot_sample_predictions(
                images[:9], predictions[:9], targets[:9], paths[:9], classes
            )
            if samples_path:
                visualizations["samples"] = samples_path

        except Exception as e:
            self.logger.error(f"Failed to generate samples: {e}")

        return visualizations

    def _plot_confusion_matrix(self, cm: "sv.ConfusionMatrix", classes: List[str]) -> str:
        """Plot and save confusion matrix."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(12, 10))
        cm.plot(ax=ax)
        ax.set_title("Confusion Matrix")

        path = str(self.output_dir / "confusion_matrix.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        return path

    def _plot_sample_predictions(
        self,
        images: List[np.ndarray],
        predictions: List["sv.Detections"],
        targets: List["sv.Detections"],
        paths: List[str],
        classes: List[str],
    ) -> Optional[str]:
        """Plot sample predictions vs ground truth."""
        import matplotlib.pyplot as plt

        n_samples = min(9, len(images))
        if n_samples == 0:
            return None

        cols = 3
        rows = (n_samples + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows))

        if rows == 1:
            axes = [axes] if cols == 1 else axes
        axes = np.array(axes).flatten()

        box_annotator = sv.BoxAnnotator()
        label_annotator = sv.LabelAnnotator()

        for i in range(n_samples):
            img = images[i].copy()
            pred = predictions[i]
            gt = targets[i]

            # Annotate predictions (green)
            if len(pred) > 0:
                labels = [
                    f"{classes[cid] if cid < len(classes) else 'unk'}: {conf:.2f}"
                    for cid, conf in zip(pred.class_id, pred.confidence or [1.0] * len(pred))
                ]
                img = box_annotator.annotate(img, pred)
                img = label_annotator.annotate(img, pred, labels)

            axes[i].imshow(img)
            axes[i].set_title(f"GT: {len(gt)}, Pred: {len(pred)}")
            axes[i].axis("off")

        for i in range(n_samples, len(axes)):
            axes[i].axis("off")

        plt.tight_layout()
        path = str(self.output_dir / "sample_predictions.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()

        return path

    def _save_metrics_summary(self, metrics: EvaluationMetrics) -> None:
        """Save metrics summary."""
        summary = {
            "map50": metrics.map50,
            "map50_95": metrics.map50_95,
            "mar50": metrics.mar50,
            "mar50_95": metrics.mar50_95,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "inference_time_per_image": metrics.inference_time_per_image,
            "total_detections": metrics.total_detections,
        }

        with open(self.output_dir / "metrics_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        try:
            import pandas as pd

            df = pd.DataFrame([summary])
            df.to_csv(self.output_dir / "evaluation_metrics.csv", index=False)
        except ImportError:
            pass

        self.logger.info(f"mAP@50: {metrics.map50:.4f}")
        self.logger.info(f"mAP@50-95: {metrics.map50_95:.4f}")
        self.logger.info(f"Precision: {metrics.precision:.4f}")
        self.logger.info(f"Recall: {metrics.recall:.4f}")
        self.logger.info(f"F1: {metrics.f1_score:.4f}")

    @staticmethod
    def _detections_to_dict(detections: "sv.Detections") -> List[Dict]:
        """Convert detections to serializable dict."""
        result = []
        for i in range(len(detections)):
            d = {
                "box": detections.xyxy[i].tolist(),
                "class_id": (int(detections.class_id[i]) if detections.class_id is not None else 0),
            }
            if detections.confidence is not None:
                d["confidence"] = float(detections.confidence[i])
            result.append(d)
        return result
