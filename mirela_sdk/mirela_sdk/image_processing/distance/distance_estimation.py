import numpy as np
from enum import Enum
from typing import Union, Optional, Dict, Any, Tuple
import logging
from mirela_sdk.image_processing.distance.distance_parameters import (
    DISTANCE_POLY_COEFFS,
    DISTANCE_CALIBRATION_CONST,
    DISTANCE_EXP_A,
    DISTANCE_EXP_B,
    DISTANCE_EXP_C,
    DISTANCE_LOG_A,
    DISTANCE_LOG_B,
    DISTANCE_K,
    DISTANCE_P,
    DISTANCE_ROBUST_A,
    DISTANCE_ROBUST_B,
    DISTANCE_ROBUST_C,
)


class EstimationMethod(Enum):
    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    EXPONENTIAL = "exponential"
    INVERSE_POWER = "inverse_power"
    LOGARITHMIC = "logarithmic"
    ROBUST_POLY2 = "robust_poly2"


class DistanceEstimationError(Exception):
    pass


class DistanceEstimator:
    def __init__(
        self,
        default_method: Union[EstimationMethod, str] = EstimationMethod.POLYNOMIAL,
        valid_range: Optional[Tuple[float, float]] = None,
        validate_inputs: bool = False,
    ):
        self.default_method = self._parse_method(default_method)
        self.valid_range = valid_range
        self.validate_inputs = validate_inputs
        self.model_params = self._load_model_parameters()
        self.logger = logging.getLogger(__name__)

    def _parse_method(self, method: Union[EstimationMethod, str]) -> EstimationMethod:
        if isinstance(method, str):
            try:
                return EstimationMethod(method.lower())
            except ValueError:
                available = [m.value for m in EstimationMethod]
                raise ValueError(
                    f"Invalid method '{method}'. Available methods: {available}"
                )
        elif isinstance(method, EstimationMethod):
            return method
        else:
            raise TypeError(
                f"Method must be string or EstimationMethod enum, got {type(method)}"
            )

    def _load_model_parameters(self) -> Dict[str, Dict[str, Any]]:
        return {
            EstimationMethod.LINEAR.value: {"k": DISTANCE_CALIBRATION_CONST},
            EstimationMethod.POLYNOMIAL.value: {"coeffs": DISTANCE_POLY_COEFFS},
            EstimationMethod.EXPONENTIAL.value: {
                "a": DISTANCE_EXP_A,
                "b": DISTANCE_EXP_B,
                "c": DISTANCE_EXP_C,
            },
            EstimationMethod.INVERSE_POWER.value: {"k": DISTANCE_K, "p": DISTANCE_P},
            EstimationMethod.LOGARITHMIC.value: {
                "a": DISTANCE_LOG_A,
                "b": DISTANCE_LOG_B,
            },
            EstimationMethod.ROBUST_POLY2.value: {
                "a": DISTANCE_ROBUST_A,
                "b": DISTANCE_ROBUST_B,
                "c": DISTANCE_ROBUST_C,
            },
        }

    def _validate_input(self, input_value: float) -> None:
        if not isinstance(input_value, (int, float)):
            raise TypeError(f"Input value must be numeric, got {type(input_value)}")

        if input_value <= 0:
            raise ValueError("Input value must be positive")

        if np.isnan(input_value) or np.isinf(input_value):
            raise ValueError("Input value must be finite")

        if self.valid_range is not None:
            min_val, max_val = self.valid_range
            if not (min_val <= input_value <= max_val):
                self.logger.warning(
                    f"Input value {input_value} is outside valid range "
                    f"{self.valid_range}. Prediction may be unreliable."
                )

    def _estimate_linear(self, input_value: float) -> float:
        k = self.model_params[EstimationMethod.LINEAR.value]["k"]
        return k / input_value

    def _estimate_polynomial(self, input_value: float) -> float:
        coeffs = self.model_params[EstimationMethod.POLYNOMIAL.value]["coeffs"]
        return np.polyval(coeffs, input_value)

    def _estimate_exponential(self, input_value: float) -> float:
        params = self.model_params[EstimationMethod.EXPONENTIAL.value]
        return params["a"] * np.exp(-params["b"] * input_value) + params["c"]

    def _estimate_inverse_power(self, input_value: float) -> float:
        params = self.model_params[EstimationMethod.INVERSE_POWER.value]
        return params["k"] / (input_value ** params["p"])

    def _estimate_logarithmic(self, input_value: float) -> float:
        params = self.model_params[EstimationMethod.LOGARITHMIC.value]
        return params["a"] * np.log(input_value) + params["b"]

    def _estimate_robust_poly2(self, input_value: float) -> float:
        params = self.model_params[EstimationMethod.ROBUST_POLY2.value]
        return params["a"] * input_value**2 + params["b"] * input_value + params["c"]

    def estimate(
        self, input_value: float, method: Optional[Union[EstimationMethod, str]] = None
    ) -> float:
        if method is None:
            method = self.default_method
        else:
            method = self._parse_method(method)

        if self.validate_inputs:
            self._validate_input(input_value)

        try:
            if method == EstimationMethod.LINEAR:
                distance = self._estimate_linear(input_value)
            elif method == EstimationMethod.POLYNOMIAL:
                distance = self._estimate_polynomial(input_value)
            elif method == EstimationMethod.EXPONENTIAL:
                distance = self._estimate_exponential(input_value)
            elif method == EstimationMethod.INVERSE_POWER:
                distance = self._estimate_inverse_power(input_value)
            elif method == EstimationMethod.LOGARITHMIC:
                distance = self._estimate_logarithmic(input_value)
            elif method == EstimationMethod.ROBUST_POLY2:
                distance = self._estimate_robust_poly2(input_value)
            else:
                raise DistanceEstimationError(f"Method {method} not implemented")

            return max(0.0, distance)

        except Exception as e:
            raise DistanceEstimationError(
                f"Distance estimation failed: {str(e)}"
            ) from e

    def estimate_distance(
        self, height_px: float, method: Optional[Union[EstimationMethod, str]] = None
    ) -> float:
        return self.estimate(height_px, method)

    def set_default_method(self, method: Union[EstimationMethod, str]) -> None:
        self.default_method = self._parse_method(method)
        self.logger.info(f"Default method set to: {self.default_method.value}")

    def set_valid_range(self, valid_range: Optional[Tuple[float, float]]) -> None:
        self.valid_range = valid_range
        if valid_range:
            self.logger.info(f"Valid range set to: {valid_range}")

    def get_available_methods(self) -> list[str]:
        return [method.value for method in EstimationMethod]

    def get_method_info(self, method: Union[EstimationMethod, str]) -> Dict[str, Any]:
        method_obj = self._parse_method(method)

        method_info = {
            EstimationMethod.LINEAR: {
                "name": "Linear (Inverse)",
                "formula": "output = k / input",
            },
            EstimationMethod.POLYNOMIAL: {
                "name": "Polynomial",
                "formula": "output = Σ(aᵢ * inputⁱ)",
            },
            EstimationMethod.EXPONENTIAL: {
                "name": "Exponential Decay",
                "formula": "output = a * exp(-b * input) + c",
            },
            EstimationMethod.INVERSE_POWER: {
                "name": "Inverse Power",
                "formula": "output = k / (input^p)",
            },
            EstimationMethod.LOGARITHMIC: {
                "name": "Logarithmic",
                "formula": "output = a * log(input) + b",
            },
            EstimationMethod.ROBUST_POLY2: {
                "name": "Robust Polynomial (Degree 2)",
                "formula": "output = a * input² + b * input + c",
            },
        }

        return method_info.get(method_obj, {"name": "Unknown", "formula": "N/A"})


if __name__ == "__main__":
    estimator = DistanceEstimator(
        default_method=EstimationMethod.EXPONENTIAL,
        valid_range=(15.0, 35.0),
        validate_inputs=True,
    )

    test_input = 25.0

    print(f"Testing with input: {test_input}")
    print("-" * 50)

    for method in EstimationMethod:
        try:
            result = estimator.estimate(test_input, method)
            print(f"{method.value:15}: {result:6.2f}")
        except Exception as e:
            print(f"{method.value:15}: Error - {e}")

    print(f"\nMethod info for {estimator.default_method.value}:")
    info = estimator.get_method_info(estimator.default_method)
    for key, value in info.items():
        print(f"  {key}: {value}")
