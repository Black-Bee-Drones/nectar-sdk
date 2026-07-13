"""
Shared AI exceptions (task-agnostic)
"""


class AIError(Exception):
    """Base exception for nectar.ai shared and task-module errors."""

    pass


class ModelNotLoadedError(AIError):
    """Raised when inference/train is called before ``load()``."""

    def __init__(self, message: str = "Model not loaded. Call load() first."):
        super().__init__(message)


class TrainingError(AIError):
    """Raised when a training run fails."""

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
