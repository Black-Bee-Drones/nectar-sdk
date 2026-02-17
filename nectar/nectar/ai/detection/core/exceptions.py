"""
Custom exceptions for the detection module.
"""


class DetectionError(Exception):
    """
    Base exception for all detection module errors.

    Examples
    --------
    >>> try:
    ...     detector.detect(image)
    ... except DetectionError as e:
    ...     logger.error(f"Detection failed: {e}")
    """

    pass


class ModelNotLoadedError(DetectionError):
    """
    Exception raised when model is not loaded.

    Examples
    --------
    >>> detector = YOLODetector("model.pt", auto_load=False)
    >>> detector.detect(image)  # Raises ModelNotLoadedError
    """

    def __init__(self, message: str = "Model not loaded. Call load() first."):
        super().__init__(message)


class TrainingError(DetectionError):
    """
    Exception raised during training.

    Parameters
    ----------
    message : str
        Error message.
    epoch : int, optional
        Epoch at which error occurred.
    step : int, optional
        Step at which error occurred.

    Examples
    --------
    >>> try:
    ...     model.train(config)
    ... except TrainingError as e:
    ...     logger.error(f"Training failed at epoch {e.epoch}: {e}")
    """

    def __init__(
        self,
        message: str,
        epoch: int = None,
        step: int = None,
    ):
        self.epoch = epoch
        self.step = step

        full_message = message
        if epoch is not None:
            full_message = f"[Epoch {epoch}] {message}"
        if step is not None:
            full_message = f"[Step {step}] {full_message}"

        super().__init__(full_message)


class EvaluationError(DetectionError):
    """
    Exception raised during evaluation.

    Parameters
    ----------
    message : str
        Error message.
    sample : str, optional
        Sample that caused the error.
    """

    def __init__(self, message: str, sample: str = None):
        self.sample = sample

        full_message = message
        if sample is not None:
            full_message = f"{message} (sample: {sample})"

        super().__init__(full_message)


class DatasetError(DetectionError):
    """
    Exception raised for dataset-related errors.

    Raised when dataset loading, parsing, or conversion fails.

    Parameters
    ----------
    message : str
        Error message.
    dataset_path : str, optional
        Path to the problematic dataset.
    """

    def __init__(self, message: str, dataset_path: str = None):
        self.dataset_path = dataset_path

        full_message = message
        if dataset_path is not None:
            full_message = f"{message} (path: {dataset_path})"

        super().__init__(full_message)


class ConfigurationError(DetectionError):
    """
    Exception raised for configuration errors.

    Parameters
    ----------
    message : str
        Error message.
    field : str, optional
        Configuration field that caused the error.
    value : any, optional
        Invalid value provided.
    """

    def __init__(
        self,
        message: str,
        field: str = None,
        value: any = None,
    ):
        self.field = field
        self.value = value

        full_message = message
        if field is not None:
            full_message = f"Configuration error in '{field}': {message}"
            if value is not None:
                full_message += f" (got: {value})"

        super().__init__(full_message)


class FrameworkError(DetectionError):
    """
    Exception raised for framework-specific errors.

    Parameters
    ----------
    message : str
        Error message.
    framework : str
        Name of the framework.
    original_error : Exception, optional
        Original exception from the framework.
    """

    def __init__(
        self,
        message: str,
        framework: str,
        original_error: Exception = None,
    ):
        self.framework = framework
        self.original_error = original_error

        full_message = f"[{framework}] {message}"
        if original_error is not None:
            full_message += f"\nOriginal error: {original_error}"

        super().__init__(full_message)


class PostProcessingError(DetectionError):
    """
    Exception raised during post-processing.

    Parameters
    ----------
    message : str
        Error message.
    strategy : str, optional
        Name of the strategy that failed.
    """

    def __init__(self, message: str, strategy: str = None):
        self.strategy = strategy

        full_message = message
        if strategy is not None:
            full_message = f"Post-processing error in '{strategy}': {message}"

        super().__init__(full_message)


class SlicingError(DetectionError):
    """
    Exception raised during slicing inference.

    Parameters
    ----------
    message : str
        Error message.
    slice_idx : int, optional
        Index of the problematic slice.
    """

    def __init__(self, message: str, slice_idx: int = None):
        self.slice_idx = slice_idx

        full_message = message
        if slice_idx is not None:
            full_message = f"Slicing error at slice {slice_idx}: {message}"

        super().__init__(full_message)


class HuggingFaceError(DetectionError):
    """
    Exception raised for HuggingFace Hub operations.

    Raised when model upload/download or repository operations fail.

    Parameters
    ----------
    message : str
        Error message.
    repo_id : str, optional
        Repository ID involved.
    operation : str, optional
        Operation that failed ('upload', 'download', 'create').
    """

    def __init__(
        self,
        message: str,
        repo_id: str = None,
        operation: str = None,
    ):
        self.repo_id = repo_id
        self.operation = operation

        full_message = message
        if repo_id is not None:
            full_message = f"HuggingFace error for '{repo_id}': {message}"
        if operation is not None:
            full_message = f"{full_message} (operation: {operation})"

        super().__init__(full_message)


class DeviceError(DetectionError):
    """
    Exception raised for device-related errors.

    Parameters
    ----------
    message : str
        Error message.
    device : str, optional
        Device that caused the error.
    """

    def __init__(self, message: str, device: str = None):
        self.device = device

        full_message = message
        if device is not None:
            full_message = f"Device error for '{device}': {message}"

        super().__init__(full_message)
