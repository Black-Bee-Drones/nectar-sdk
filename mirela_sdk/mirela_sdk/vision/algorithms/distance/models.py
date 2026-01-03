from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum, auto
import numpy as np


class ModelType(Enum):
    """
    Enumeration of available distance estimation model types.

    Attributes
    ----------
    LINEAR : auto
        Simple inverse linear model.
    POLYNOMIAL : auto
        Polynomial regression model.
    EXPONENTIAL : auto
        Exponential decay model.
    LOGARITHMIC : auto
        Logarithmic model.
    INVERSE_POWER : auto
        Inverse power law model.
    ROBUST_POLY2 : auto
        Robust polynomial degree 2 model.
    """

    LINEAR = auto()
    POLYNOMIAL = auto()
    EXPONENTIAL = auto()
    LOGARITHMIC = auto()
    INVERSE_POWER = auto()
    ROBUST_POLY2 = auto()


@dataclass
class ModelParams:
    """
    Container for model type and its fitted parameters.

    Parameters
    ----------
    model_type : ModelType
        The type of estimation model.
    params : Dict[str, Any]
        Dictionary of model-specific parameters.
    """

    model_type: ModelType
    params: Dict[str, Any]

    @property
    def name(self) -> str:
        """Lowercase name of the model type."""
        return self.model_type.name.lower()


class EstimationModel(ABC):
    """
    Abstract base class for distance estimation models.
    """

    @abstractmethod
    def estimate(self, value: float) -> float:
        """
        Estimate distance from pixel measurement.

        Parameters
        ----------
        value : float
            Pixel measurement (e.g., object height in pixels).

        Returns
        -------
        float
            Estimated distance in the calibrated unit (typically cm).
        """
        pass

    @abstractmethod
    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit model parameters to calibration data.

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements (independent variable).
        y : np.ndarray
            Corresponding real distances (dependent variable).

        Returns
        -------
        Dict[str, Any]
            Dictionary of fitted parameter names and values.
        """
        pass


class LinearModel(EstimationModel):
    """
    Simple inverse linear model: distance = k / pixels.

    Parameters
    ----------
    k : float, default=2150.0
        Proportionality constant (distance * pixels).

    Attributes
    ----------
    k : float
        The calibrated proportionality constant.
    """

    def __init__(self, k: float = 2150.0):
        self.k = k

    def estimate(self, value: float) -> float:
        """
        Estimate distance using inverse linear model.

        Parameters
        ----------
        value : float
            Pixel measurement.

        Returns
        -------
        float
            Estimated distance. Returns inf if value <= 0.
        """
        if value <= 0:
            return float("inf")
        return self.k / value

    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit k parameter as mean of (distance * pixels).

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements.
        y : np.ndarray
            Real distances.

        Returns
        -------
        Dict[str, Any]
            Dictionary with fitted 'k' value.
        """
        self.k = float(np.mean(y * x))
        return {"k": self.k}


class PolynomialModel(EstimationModel):
    """
    Polynomial regression model for distance estimation.

    Parameters
    ----------
    coeffs : list, optional
        Polynomial coefficients (highest degree first).
    degree : int, default=4
        Degree of polynomial to fit.

    Attributes
    ----------
    coeffs : list
        Fitted polynomial coefficients.
    degree : int
        Polynomial degree.
    """

    def __init__(self, coeffs: list = None, degree: int = 4):
        self.coeffs = coeffs or []
        self.degree = degree

    def estimate(self, value: float) -> float:
        """
        Estimate distance using polynomial evaluation.

        Parameters
        ----------
        value : float
            Pixel measurement.

        Returns
        -------
        float
            Estimated distance (clamped to >= 0). Returns inf if value <= 0.
        """
        if value <= 0:
            return float("inf")
        return max(0.0, float(np.polyval(self.coeffs, value)))

    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit polynomial coefficients using least squares.

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements.
        y : np.ndarray
            Real distances.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'coeffs' list and 'degree' value.
        """
        self.coeffs = np.polyfit(x, y, self.degree).tolist()
        return {"coeffs": self.coeffs, "degree": self.degree}


class ExponentialModel(EstimationModel):
    """
    Exponential decay model: distance = a * exp(-b * pixels) + c.

    Parameters
    ----------
    a : float, default=764.0
        Amplitude of exponential decay.
    b : float, default=0.1
        Decay rate constant.
    c : float, default=24.8
        Asymptotic offset.

    Attributes
    ----------
    a, b, c : float
        Fitted model parameters.
    """

    def __init__(self, a: float = 764.0, b: float = 0.1, c: float = 24.8):
        self.a = a
        self.b = b
        self.c = c

    def estimate(self, value: float) -> float:
        """
        Estimate distance using exponential decay model.

        Parameters
        ----------
        value : float
            Pixel measurement.

        Returns
        -------
        float
            Estimated distance (clamped to >= 0). Returns inf if value <= 0.
        """
        if value <= 0:
            return float("inf")
        return max(0.0, self.a * np.exp(-self.b * value) + self.c)

    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit exponential parameters using nonlinear least squares.

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements.
        y : np.ndarray
            Real distances.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'a', 'b', 'c' parameters.
        """
        from scipy.optimize import curve_fit

        def func(h, a, b, c):
            return a * np.exp(-b * h) + c

        popt, _ = curve_fit(func, x, y, p0=[100, 0.1, 10], maxfev=2000)
        self.a, self.b, self.c = popt
        return {"a": float(self.a), "b": float(self.b), "c": float(self.c)}


class LogarithmicModel(EstimationModel):
    """
    Logarithmic model: distance = a * ln(pixels) + b.

    Parameters
    ----------
    a : float, default=-173.7
        Logarithmic coefficient (typically negative).
    b : float, default=637.5
        Offset constant.

    Attributes
    ----------
    a, b : float
        Fitted model parameters.
    """

    def __init__(self, a: float = -173.7, b: float = 637.5):
        self.a = a
        self.b = b

    def estimate(self, value: float) -> float:
        """
        Estimate distance using logarithmic model.

        Parameters
        ----------
        value : float
            Pixel measurement.

        Returns
        -------
        float
            Estimated distance (clamped to >= 0). Returns inf if value <= 0.
        """
        if value <= 0:
            return float("inf")
        return max(0.0, self.a * np.log(value) + self.b)

    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit logarithmic parameters using nonlinear least squares.

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements.
        y : np.ndarray
            Real distances.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'a', 'b' parameters.
        """
        from scipy.optimize import curve_fit

        def func(h, a, b):
            return a * np.log(h) + b

        popt, _ = curve_fit(func, x, y)
        self.a, self.b = popt
        return {"a": float(self.a), "b": float(self.b)}


class InversePowerModel(EstimationModel):
    """
    Inverse power law model: distance = k / (pixels ^ p).

    Parameters
    ----------
    k : float, default=10000.0
        Proportionality constant.
    p : float, default=1.5
        Power exponent.

    Attributes
    ----------
    k, p : float
        Fitted model parameters.
    """

    def __init__(self, k: float = 10000.0, p: float = 1.5):
        self.k = k
        self.p = p

    def estimate(self, value: float) -> float:
        """
        Estimate distance using inverse power model.

        Parameters
        ----------
        value : float
            Pixel measurement.

        Returns
        -------
        float
            Estimated distance. Returns inf if value <= 0.
        """
        if value <= 0:
            return float("inf")
        return self.k / (value**self.p)

    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit inverse power parameters using bounded nonlinear least squares.

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements.
        y : np.ndarray
            Real distances.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'k', 'p' parameters.
        """
        from scipy.optimize import curve_fit

        def func(h, k, p):
            return k / (h**p)

        popt, _ = curve_fit(func, x, y, p0=[2150, 1], bounds=([0, 0.1], [10000, 3]))
        self.k, self.p = popt
        return {"k": float(self.k), "p": float(self.p)}


class RobustPoly2Model(EstimationModel):
    """
    Robust quadratic polynomial using Huber regression.

    Parameters
    ----------
    a : float, default=0.39
        Quadratic coefficient (x² term).
    b : float, default=-25.6
        Linear coefficient (x term).
    c : float, default=234.2
        Constant term.

    Attributes
    ----------
    a, b, c : float
        Fitted model parameters.
    """

    def __init__(self, a: float = 0.39, b: float = -25.6, c: float = 234.2):
        self.a = a
        self.b = b
        self.c = c

    def estimate(self, value: float) -> float:
        """
        Estimate distance using robust quadratic model.

        Parameters
        ----------
        value : float
            Pixel measurement.

        Returns
        -------
        float
            Estimated distance (clamped to >= 0). Returns inf if value <= 0.
        """
        if value <= 0:
            return float("inf")
        return max(0.0, self.a * value**2 + self.b * value + self.c)

    def fit(self, x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Fit quadratic parameters using Huber robust regression.

        Parameters
        ----------
        x : np.ndarray
            Pixel measurements.
        y : np.ndarray
            Real distances.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'a', 'b', 'c' parameters.
        """
        from sklearn.linear_model import HuberRegressor

        X = np.column_stack([x**2, x, np.ones(len(x))])
        huber = HuberRegressor(epsilon=1.5, max_iter=200)
        huber.fit(X, y)
        self.a, self.b = huber.coef_[:2]
        self.c = huber.intercept_
        return {"a": float(self.a), "b": float(self.b), "c": float(self.c)}


MODEL_REGISTRY: Dict[ModelType, type] = {
    ModelType.LINEAR: LinearModel,
    ModelType.POLYNOMIAL: PolynomialModel,
    ModelType.EXPONENTIAL: ExponentialModel,
    ModelType.LOGARITHMIC: LogarithmicModel,
    ModelType.INVERSE_POWER: InversePowerModel,
    ModelType.ROBUST_POLY2: RobustPoly2Model,
}


def create_model(
    model_type: ModelType, params: Dict[str, Any] = None
) -> EstimationModel:
    """
    Factory function to create estimation model instances.

    Parameters
    ----------
    model_type : ModelType
        Type of model to create.
    params : Dict[str, Any], optional
        Model-specific parameters. If None, uses defaults.

    Returns
    -------
    EstimationModel
        Configured model instance.

    Raises
    ------
    ValueError
        If model_type is not in MODEL_REGISTRY.

    Examples
    --------
    >>> model = create_model(ModelType.POLYNOMIAL, {"degree": 3})
    >>> distance = model.estimate(25.0)
    """
    model_class = MODEL_REGISTRY.get(model_type)
    if model_class is None:
        raise ValueError(f"Unknown model type: {model_type}")
    return model_class(**(params or {}))
