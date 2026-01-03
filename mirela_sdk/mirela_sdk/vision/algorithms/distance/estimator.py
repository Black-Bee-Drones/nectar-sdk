from pathlib import Path
from typing import Optional, Dict, Any, Union
import yaml
import numpy as np

from mirela_sdk.vision.algorithms.distance.models import (
    ModelType,
    EstimationModel,
    create_model,
)


class DistanceEstimator:
    """
    Estimate distances from pixel measurements using calibrated models.

    Parameters
    ----------
    model_type : Union[ModelType, str], optional
        Model to use for estimation. If None, uses default from config.
    params_path : Path, optional
        Path to parameters YAML file. If None, uses default location.
    custom_params : Dict[str, Any], optional
        Override parameters for specific models.

    Attributes
    ----------
    model : EstimationModel
        Currently active estimation model.
    model_type : ModelType
        Type of the active model.

    Examples
    --------
    >>> estimator = DistanceEstimator(model_type="polynomial")
    >>> estimator.estimate(21.6)  # pixels -> cm
    97.7

    >>> estimator.compare_methods(21.6)
    {'linear': 101.9, 'polynomial': 97.7, 'exponential': 97.8, ...}
    """

    DEFAULT_PARAMS_PATH = Path(__file__).parent / "parameters.yaml"

    def __init__(
        self,
        model_type: Union[ModelType, str] = None,
        params_path: Optional[Path] = None,
        custom_params: Optional[Dict[str, Any]] = None,
    ):
        self._params = self._load_params(params_path or self.DEFAULT_PARAMS_PATH)

        if custom_params:
            self._params.update(custom_params)

        model_type = model_type or self._params.get("default_method", "polynomial")
        self._model_type = self._parse_model_type(model_type)
        self._models: Dict[ModelType, EstimationModel] = {}
        self._initialize_models()

    def _load_params(self, path: Path) -> Dict[str, Any]:
        """
        Load parameters from YAML file.

        Parameters
        ----------
        path : Path
            Path to YAML configuration file.

        Returns
        -------
        Dict[str, Any]
            Loaded parameters or empty dict if file not found.
        """
        if not path.exists():
            return {}
        with open(path) as f:
            return yaml.safe_load(f)

    def _parse_model_type(self, model_type: Union[ModelType, str]) -> ModelType:
        """
        Convert string to ModelType enum.

        Parameters
        ----------
        model_type : Union[ModelType, str]
            Model type as enum or string.

        Returns
        -------
        ModelType
            Parsed model type enum.

        Raises
        ------
        KeyError
            If string does not match any ModelType.
        """
        if isinstance(model_type, ModelType):
            return model_type
        return ModelType[model_type.upper()]

    def _initialize_models(self) -> None:
        """Initialize all model types from loaded parameters."""
        for model_type in ModelType:
            key = model_type.name.lower()
            params = self._params.get(key, {})
            self._models[model_type] = create_model(model_type, params)

    @property
    def model(self) -> EstimationModel:
        """Currently active estimation model instance."""
        return self._models[self._model_type]

    @property
    def model_type(self) -> ModelType:
        """Type of the currently active model."""
        return self._model_type

    @model_type.setter
    def model_type(self, value: Union[ModelType, str]) -> None:
        """Set the active model type."""
        self._model_type = self._parse_model_type(value)

    def estimate(
        self,
        value: float,
        model_type: Optional[Union[ModelType, str]] = None,
    ) -> float:
        """
        Estimate distance from pixel measurement.

        Parameters
        ----------
        value : float
            Pixel measurement (e.g., object height in pixels).
        model_type : Union[ModelType, str], optional
            Override model type for this estimation. If None, uses default.

        Returns
        -------
        float
            Estimated distance in calibrated units (typically cm).

        Examples
        --------
        >>> estimator.estimate(21.6)
        97.7
        >>> estimator.estimate(21.6, model_type="linear")
        101.9
        """
        if model_type is not None:
            model = self._models[self._parse_model_type(model_type)]
        else:
            model = self.model
        return model.estimate(value)

    def estimate_batch(
        self,
        values: np.ndarray,
        model_type: Optional[Union[ModelType, str]] = None,
    ) -> np.ndarray:
        """
        Estimate distances for multiple pixel measurements.

        Parameters
        ----------
        values : np.ndarray
            Array of pixel measurements.
        model_type : Union[ModelType, str], optional
            Override model type. If None, uses default.

        Returns
        -------
        np.ndarray
            Array of estimated distances.

        Examples
        --------
        >>> pixels = np.array([15, 20, 25, 30])
        >>> estimator.estimate_batch(pixels)
        array([173.3, 112.5, 73.2, 53.4])
        """
        return np.array([self.estimate(v, model_type) for v in values])

    def compare_methods(self, value: float) -> Dict[str, float]:
        """
        Compare estimates from all available models.

        Parameters
        ----------
        value : float
            Pixel measurement to estimate.

        Returns
        -------
        Dict[str, float]
            Dictionary mapping model names to estimated distances.

        Examples
        --------
        >>> estimator.compare_methods(21.6)
        {'linear': 101.9, 'polynomial': 97.7, 'exponential': 97.8, ...}
        """
        return {
            model_type.name.lower(): self._models[model_type].estimate(value)
            for model_type in ModelType
        }

    def get_model(self, model_type: Union[ModelType, str]) -> EstimationModel:
        """
        Get specific model instance.

        Parameters
        ----------
        model_type : Union[ModelType, str]
            Model type to retrieve.

        Returns
        -------
        EstimationModel
            The requested model instance.
        """
        return self._models[self._parse_model_type(model_type)]

    def set_model_params(
        self, model_type: Union[ModelType, str], params: Dict[str, Any]
    ) -> None:
        """
        Update parameters for a specific model.

        Parameters
        ----------
        model_type : Union[ModelType, str]
            Model to update.
        params : Dict[str, Any]
            New parameter values.
        """
        mt = self._parse_model_type(model_type)
        self._models[mt] = create_model(mt, params)

    @staticmethod
    def available_methods() -> list:
        """
        Get list of available estimation methods.

        Returns
        -------
        list
            List of model type names (lowercase).
        """
        return [m.name.lower() for m in ModelType]
