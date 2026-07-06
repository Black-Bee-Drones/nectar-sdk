"""Detection filtering strategies."""

from pathlib import Path
from typing import Dict, Optional

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None


class PerClassConfidenceFilter:
    """
    Filter detections using per-class confidence thresholds.

    Thresholds can be provided as a dict or loaded from a CSV file
    (e.g. pr_analysis_results.csv from evaluation).

    Parameters
    ----------
    threshold_mapping : dict, optional
        Mapping of class_id to confidence threshold.
    default_threshold : float
        Default threshold for classes not in mapping. Defaults to 0.25.
    csv_path : str, optional
        Path to CSV with columns class_id and optimal_threshold.
    """

    def __init__(
        self,
        threshold_mapping: Optional[Dict[int, float]] = None,
        default_threshold: float = 0.25,
        csv_path: Optional[str] = None,
    ):
        self.default_threshold = default_threshold

        if csv_path and Path(csv_path).exists():
            self.threshold_mapping = self._load_from_csv(csv_path)
        elif threshold_mapping:
            self.threshold_mapping = threshold_mapping
        else:
            self.threshold_mapping = {}

    @staticmethod
    def _load_from_csv(csv_path: str) -> Dict[int, float]:
        import pandas as pd

        df = pd.read_csv(csv_path)
        mapping = {}
        if "class_id" in df.columns and "optimal_threshold" in df.columns:
            for _, row in df.iterrows():
                mapping[int(row["class_id"])] = float(row["optimal_threshold"])
        return mapping

    def filter(self, detections: "sv.Detections") -> "sv.Detections":
        if len(detections) == 0 or detections.confidence is None:
            return detections

        keep = np.zeros(len(detections), dtype=bool)
        for i, (cls_id, conf) in enumerate(zip(detections.class_id, detections.confidence)):
            threshold = self.threshold_mapping.get(int(cls_id), self.default_threshold)
            keep[i] = conf >= threshold

        return detections[keep]
