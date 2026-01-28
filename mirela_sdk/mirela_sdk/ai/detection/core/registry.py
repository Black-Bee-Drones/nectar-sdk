import logging
from typing import Any, Callable, Dict, List, Optional, Type, TYPE_CHECKING
import os

if TYPE_CHECKING:
    from .base import BaseDetectionModel

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Singleton registry for detection model classes.

    Examples
    --------
    >>> # Register a model class
    >>> @ModelRegistry.register("ultralytics")
    ... class UltralyticsModel(BaseDetectionModel):
    ...     pass

    >>> # Get registered model class
    >>> model_cls = ModelRegistry.get("ultralytics")
    >>> model = model_cls("yolov8n.pt")

    >>> # Create model instance directly
    >>> model = ModelRegistry.create("ultralytics", "yolov8n.pt", config)

    >>> # List registered models
    >>> ModelRegistry.list_models()
    ['ultralytics', 'transformers', 'rfdetr']
    """

    _models: Dict[str, Type["BaseDetectionModel"]] = {}
    _factories: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str) -> Callable:
        """
        Decorator to register a model class.

        Parameters
        ----------
        name : str
            Identifier for the model type.

        Returns
        -------
        Callable
            Decorator function.

        Examples
        --------
        >>> @ModelRegistry.register("my_model")
        ... class MyModel(BaseDetectionModel):
        ...     pass
        """

        def decorator(
            model_cls: Type["BaseDetectionModel"],
        ) -> Type["BaseDetectionModel"]:
            if name in cls._models:
                logger.warning(f"Overwriting existing model registration: {name}")
            cls._models[name] = model_cls
            logger.debug(f"Registered model: {name} -> {model_cls.__name__}")
            return model_cls

        return decorator

    @classmethod
    def register_factory(cls, name: str, factory_func: Callable) -> None:
        """
        Register a factory function for creating models.

        Parameters
        ----------
        name : str
            Identifier for the model type.
        factory_func : Callable
            Factory function that creates model instances.

        Examples
        --------
        >>> def create_custom_model(model_name, config):
        ...     return CustomModel(model_name, **config)
        >>> ModelRegistry.register_factory("custom", create_custom_model)
        """
        cls._factories[name] = factory_func
        logger.debug(f"Registered factory: {name}")

    @classmethod
    def get(cls, name: str) -> Type["BaseDetectionModel"]:
        """
        Get a registered model class by name.

        Parameters
        ----------
        name : str
            Model type identifier.

        Returns
        -------
        Type[BaseDetectionModel]
            Registered model class.

        Raises
        ------
        ValueError
            If model type is not registered.

        Examples
        --------
        >>> model_cls = ModelRegistry.get("ultralytics")
        >>> model = model_cls("yolov8n.pt")
        """
        if name not in cls._models:
            available = cls.list_models()
            raise ValueError(
                f"Model '{name}' not found in registry. "
                f"Available models: {available}"
            )
        return cls._models[name]

    @classmethod
    def create(
        cls,
        name: str,
        model_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> "BaseDetectionModel":
        """
        Create a model instance.

        Parameters
        ----------
        name : str
            Model type identifier ('ultralytics', 'transformers', 'rfdetr').
        model_name : str
            Specific model name (e.g., 'yolov8n.pt', 'facebook/detr-resnet-50').
        config : Optional[Dict[str, Any]], optional
            Model configuration dictionary.

        Returns
        -------
        BaseDetectionModel
            Model instance.

        Raises
        ------
        ValueError
            If model type is not registered.

        Examples
        --------
        >>> model = ModelRegistry.create(
        ...     "ultralytics",
        ...     "yolov8n.pt",
        ...     {"device": "cuda", "confidence_threshold": 0.5}
        ... )
        """
        config = config or {}

        if name in cls._factories:
            return cls._factories[name](model_name, config)

        model_cls = cls.get(name)
        return model_cls(model_name, **config)

    @classmethod
    def list_models(cls) -> List[str]:
        """
        List all registered model names.

        Returns
        -------
        List[str]
            List of registered model identifiers.
        """
        return sorted(set(list(cls._models.keys()) + list(cls._factories.keys())))

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a model type is registered.

        Parameters
        ----------
        name : str
            Model type identifier.

        Returns
        -------
        bool
            True if registered.
        """
        return name in cls._models or name in cls._factories

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (useful for testing)."""
        cls._models.clear()
        cls._factories.clear()


registry = ModelRegistry


class DetectorFactory:
    """
    Factory class for creating detection model instances.

    Provides high-level methods for model creation from various sources.

    Examples
    --------
    >>> # Create from framework and model name
    >>> model = DetectorFactory.create(
    ...     framework="ultralytics",
    ...     model_source="yolov8n.pt",
    ...     config={"device": "cuda"}
    ... )

    >>> # Create from HuggingFace Hub
    >>> model = DetectorFactory.from_pretrained("user/my-model")

    >>> # Create from checkpoint
    >>> model = DetectorFactory.from_checkpoint("/path/to/checkpoint.pt")
    """

    @staticmethod
    def create(
        framework: str,
        model_source: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> "BaseDetectionModel":
        """
        Create a model instance.

        Parameters
        ----------
        framework : str
            Model framework ('ultralytics', 'transformers', 'rfdetr').
        model_source : str
            Model path, name, or HuggingFace ID.
        config : Optional[Dict[str, Any]], optional
            Model configuration.

        Returns
        -------
        BaseDetectionModel
            Model instance.
        """
        return ModelRegistry.create(framework, model_source, config)

    @staticmethod
    def from_pretrained(
        model_id: str,
        framework: Optional[str] = None,
        **kwargs,
    ) -> "BaseDetectionModel":
        """
        Create model from HuggingFace Hub or pretrained weights.

        Parameters
        ----------
        model_id : str
            HuggingFace model ID or local path.
        framework : Optional[str], optional
            Framework to use. Auto-detected if not provided.
        **kwargs
            Additional model configuration.

        Returns
        -------
        BaseDetectionModel
            Model instance.
        """
        if framework is None:
            if any(x in model_id.lower() for x in ["yolo", "ultralytics"]):
                framework = "ultralytics"
            elif any(x in model_id.lower() for x in ["detr", "facebook", "microsoft"]):
                framework = "transformers"
            elif "rfdetr" in model_id.lower():
                framework = "rfdetr"
            else:
                # Default to ultralytics for .pt files
                framework = "ultralytics"

        model = ModelRegistry.create(framework, model_id, kwargs)
        model.load_model()
        return model

    @staticmethod
    def from_checkpoint(
        checkpoint_path: str,
        framework: Optional[str] = None,
        **kwargs,
    ) -> "BaseDetectionModel":
        """
        Load model from checkpoint file.

        Parameters
        ----------
        checkpoint_path : str
            Path to checkpoint file.
        framework : Optional[str], optional
            Framework to use. Auto-detected if not provided.
        **kwargs
            Additional model configuration.

        Returns
        -------
        BaseDetectionModel
            Model instance.

        Raises
        ------
        FileNotFoundError
            If checkpoint file doesn't exist.
        """
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

        if framework is None:
            if checkpoint_path.endswith(".pt"):
                import torch

                try:
                    checkpoint = torch.load(checkpoint_path, map_location="cpu")
                    if "model" in checkpoint and "config" in checkpoint:
                        config = checkpoint.get("config", {})
                        if "model_type" in config:
                            framework = config["model_type"]
                except Exception:
                    pass

                if framework is None:
                    framework = "ultralytics"
            else:
                framework = "transformers"

        model = ModelRegistry.create(framework, checkpoint_path, kwargs)
        model.load_model(checkpoint_path)
        return model
