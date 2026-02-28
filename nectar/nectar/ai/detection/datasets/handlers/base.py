"""Base class for dataset download handlers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class BaseDatasetHandler(ABC):
    """
    Abstract base class for dataset download handlers.

    All dataset handlers should inherit from this class and implement
    the required methods for downloading and converting datasets.

    Examples
    --------
    >>> class CustomHandler(BaseDatasetHandler):
    ...     def download(self, **kwargs) -> Path:
    ...         # Implementation
    ...         pass
    ...     def convert(self, format: str, **kwargs) -> str:
    ...         # Implementation
    ...         pass
    """

    def __init__(self, output_dir: str, verbose: bool = True):
        """
        Initialize handler.

        Parameters
        ----------
        output_dir : str
            Output directory for downloaded dataset.
        verbose : bool, optional
            Print progress information. Defaults to True.
        """
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.verbose = verbose
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def download(self, **kwargs) -> Path:
        """
        Download dataset.

        Returns
        -------
        Path
            Path to downloaded dataset directory.
        """
        pass

    @abstractmethod
    def convert(self, format: str, **kwargs) -> Optional[str]:
        """
        Convert dataset to specified format.

        Parameters
        ----------
        format : str
            Target format ("yolo", "coco", etc.).

        Returns
        -------
        str or None
            Path to converted dataset or config file, if applicable.
        """
        pass

    def _print(self, message: str) -> None:
        """Print message if verbose."""
        if self.verbose:
            print(message)
