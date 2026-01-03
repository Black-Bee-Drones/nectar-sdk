import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from .distance_estimation import DistanceEstimator, EstimationMethod
from .distance_parameters import *


class DistanceCalibrator:
    def __init__(self):
        self.data_points: List[Tuple[float, float]] = []
        self.calibrated_params: Dict[str, Dict[str, Any]] = {}

    def add_data_point(
        self, measured_distance: float, pixel_measurement: float
    ) -> None:
        self.data_points.append((measured_distance, pixel_measurement))

    def add_data_points(self, data_points: List[Tuple[float, float]]) -> None:
        self.data_points.extend(data_points)

    def clear_data_points(self) -> None:
        self.data_points.clear()

    def get_data_points(self) -> List[Tuple[float, float]]:
        return self.data_points.copy()

    def calibrate_linear(self) -> Dict[str, float]:
        if len(self.data_points) < 2:
            raise ValueError("At least 2 data points required for linear calibration")

        distances = np.array([point[0] for point in self.data_points])
        pixels = np.array([point[1] for point in self.data_points])

        k = np.mean(distances * pixels)

        estimator = DistanceEstimator(default_method=EstimationMethod.LINEAR)
        estimator.model_params[EstimationMethod.LINEAR.value]["k"] = k

        predictions = k / pixels
        mse = np.mean((predictions - distances) ** 2)
        rmse = np.sqrt(mse)
        r2 = 1 - (
            np.sum((distances - predictions) ** 2)
            / np.sum((distances - np.mean(distances)) ** 2)
        )

        result = {"k": k, "rmse": rmse, "r2": r2, "mse": mse}

        self.calibrated_params["linear"] = result
        return result

    def calibrate_polynomial(self, degree: int = 2) -> Dict[str, Any]:
        if len(self.data_points) < degree + 1:
            raise ValueError(
                f"At least {degree + 1} data points required for polynomial degree {degree}"
            )

        distances = np.array([point[0] for point in self.data_points])
        pixels = np.array([point[1] for point in self.data_points])

        coeffs = np.polyfit(pixels, distances, degree)
        predictions = np.polyval(coeffs, pixels)

        mse = np.mean((predictions - distances) ** 2)
        rmse = np.sqrt(mse)
        r2 = 1 - (
            np.sum((distances - predictions) ** 2)
            / np.sum((distances - np.mean(distances)) ** 2)
        )

        result = {
            "coeffs": coeffs.tolist(),
            "degree": degree,
            "rmse": rmse,
            "r2": r2,
            "mse": mse,
        }

        self.calibrated_params[f"polynomial_{degree}"] = result
        return result

    def get_best_calibration(self) -> Tuple[str, Dict[str, Any]]:
        if not self.calibrated_params:
            raise ValueError("No calibrations performed. Run calibrate methods first.")

        best_name = min(
            self.calibrated_params.keys(),
            key=lambda x: self.calibrated_params[x]["rmse"],
        )
        return best_name, self.calibrated_params[best_name]

    def create_estimator_from_calibration(
        self,
        calibration_name: Optional[str] = None,
        valid_range: Optional[Tuple[float, float]] = None,
    ) -> DistanceEstimator:
        if not self.calibrated_params:
            raise ValueError("No calibrations performed. Run calibrate methods first.")

        if calibration_name is None:
            calibration_name, _ = self.get_best_calibration()

        if calibration_name not in self.calibrated_params:
            available = list(self.calibrated_params.keys())
            raise ValueError(
                f"Calibration '{calibration_name}' not found. Available: {available}"
            )

        calib_data = self.calibrated_params[calibration_name]

        if calibration_name == "linear":
            estimator = DistanceEstimator(
                default_method=EstimationMethod.LINEAR,
                valid_range=valid_range,
                validate_inputs=True,
            )
            estimator.model_params[EstimationMethod.LINEAR.value]["k"] = calib_data["k"]

        elif calibration_name.startswith("polynomial"):
            estimator = DistanceEstimator(
                default_method=EstimationMethod.POLYNOMIAL,
                valid_range=valid_range,
                validate_inputs=True,
            )
            estimator.model_params[EstimationMethod.POLYNOMIAL.value]["coeffs"] = (
                calib_data["coeffs"]
            )

        else:
            raise ValueError(f"Unsupported calibration type: {calibration_name}")

        return estimator

    def evaluate_estimator(
        self, estimator: DistanceEstimator, method: EstimationMethod
    ) -> Dict[str, float]:
        if not self.data_points:
            raise ValueError("No data points available for evaluation")

        distances = np.array([point[0] for point in self.data_points])
        pixels = np.array([point[1] for point in self.data_points])

        predictions = np.array([estimator.estimate(pixel, method) for pixel in pixels])

        mse = np.mean((predictions - distances) ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(predictions - distances))
        r2 = 1 - (
            np.sum((distances - predictions) ** 2)
            / np.sum((distances - np.mean(distances)) ** 2)
        )

        return {"rmse": rmse, "mae": mae, "r2": r2, "mse": mse}

    def generate_parameter_code(self, calibration_name: Optional[str] = None) -> str:
        if calibration_name is None:
            calibration_name, _ = self.get_best_calibration()

        calib_data = self.calibrated_params[calibration_name]

        if calibration_name == "linear":
            return f"""
DISTANCE_CALIBRATION_CONST = {calib_data['k']:.6f}

estimator = DistanceEstimator(default_method=EstimationMethod.LINEAR)
distance = estimator.estimate(pixel_value)
"""
        elif calibration_name.startswith("polynomial"):
            coeffs_str = (
                "[" + ", ".join([f"{c:.6f}" for c in calib_data["coeffs"]]) + "]"
            )
            return f"""
DISTANCE_POLY_COEFFS = {coeffs_str}

estimator = DistanceEstimator(default_method=EstimationMethod.POLYNOMIAL)
distance = estimator.estimate(pixel_value)
"""
        else:
            return f"# Code generation for {calibration_name} not implemented"
