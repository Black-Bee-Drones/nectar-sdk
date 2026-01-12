"""
Device management utilities.
"""

import logging
from typing import Optional, Union

try:
    import torch
except ImportError:
    torch = None


logger = logging.getLogger(__name__)


def get_device(device: Optional[str] = None) -> "torch.device":
    """
    Get torch device from string specification.

    Parameters
    ----------
    device : Optional[str], optional
        Device specification. Options:
        - None or "auto": Auto-detect (CUDA > MPS > CPU)
        - "cpu": CPU
        - "cuda": First CUDA device
        - "cuda:N": Specific CUDA device
        - "mps": Metal Performance Shaders (Apple Silicon)
        - "N": Specific CUDA device by index

    Returns
    -------
    torch.device
        Resolved device.

    Examples
    --------
    >>> device = get_device("auto")
    >>> device = get_device("cuda:0")
    >>> device = get_device("cpu")
    """
    if torch is None:
        raise ImportError("PyTorch is required. Install with: pip install torch")

    if device is None or device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        else:
            return torch.device("cpu")

    if device == "cpu":
        return torch.device("cpu")

    if device == "mps":
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        logger.warning("MPS not available, falling back to CPU")
        return torch.device("cpu")

    # Handle CUDA
    if device.startswith("cuda"):
        if torch.cuda.is_available():
            return torch.device(device)
        logger.warning(f"CUDA not available, falling back to CPU")
        return torch.device("cpu")

    # Handle numeric index
    if device.isdigit():
        if torch.cuda.is_available():
            idx = int(device)
            if idx < torch.cuda.device_count():
                return torch.device(f"cuda:{idx}")
            logger.warning(f"GPU {idx} not available, using cuda:0")
            return torch.device("cuda:0")
        logger.warning("CUDA not available, falling back to CPU")
        return torch.device("cpu")

    # Default
    logger.warning(f"Unknown device '{device}', falling back to CPU")
    return torch.device("cpu")


class DeviceManager:
    """
    Manager for device allocation and memory.

    Examples
    --------
    >>> manager = DeviceManager()
    >>> device = manager.get_best_device()
    >>> manager.log_memory_usage()
    >>> manager.clear_cache()
    """

    def __init__(self):
        """Initialize device manager."""
        self._device_cache = {}

    def get_best_device(
        self,
        prefer_gpu: bool = True,
        min_memory_gb: float = 0.0,
    ) -> "torch.device":
        """
        Get best available device.

        Parameters
        ----------
        prefer_gpu : bool, optional
            Prefer GPU over CPU. Defaults to True.
        min_memory_gb : float, optional
            Minimum GPU memory required. Defaults to 0.0.

        Returns
        -------
        torch.device
            Best available device.
        """
        if torch is None:
            raise ImportError("PyTorch is required")

        if not prefer_gpu:
            return torch.device("cpu")

        if torch.cuda.is_available():
            # Find GPU with enough memory
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                memory_gb = props.total_memory / 1024**3
                if memory_gb >= min_memory_gb:
                    return torch.device(f"cuda:{i}")

            # Fall back to first GPU
            return torch.device("cuda:0")

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")

        return torch.device("cpu")

    def get_memory_info(self, device: Optional["torch.device"] = None) -> dict:
        """
        Get memory information for device.

        Parameters
        ----------
        device : Optional[torch.device], optional
            Device to query. Defaults to current CUDA device.

        Returns
        -------
        dict
            Memory information.
        """
        if torch is None or not torch.cuda.is_available():
            return {}

        if device is None:
            device = torch.device("cuda")

        if not str(device).startswith("cuda"):
            return {}

        idx = device.index if device.index is not None else 0
        return {
            "allocated_gb": torch.cuda.memory_allocated(idx) / 1024**3,
            "reserved_gb": torch.cuda.memory_reserved(idx) / 1024**3,
            "max_allocated_gb": torch.cuda.max_memory_allocated(idx) / 1024**3,
        }

    def log_memory_usage(self, device: Optional["torch.device"] = None) -> None:
        """
        Log memory usage to logger.

        Parameters
        ----------
        device : Optional[torch.device], optional
            Device to query.
        """
        info = self.get_memory_info(device)
        if info:
            logger.info(
                f"GPU Memory: {info['allocated_gb']:.2f}GB allocated, "
                f"{info['reserved_gb']:.2f}GB reserved"
            )

    def clear_cache(self) -> None:
        """Clear GPU cache."""
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.debug("Cleared CUDA cache")

    def set_memory_fraction(self, fraction: float = 0.9) -> None:
        """
        Set maximum memory fraction per GPU.

        Parameters
        ----------
        fraction : float, optional
            Fraction of GPU memory to use (0.0 to 1.0). Defaults to 0.9.
        """
        if torch is not None and torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(fraction)
            logger.info(f"Set GPU memory fraction to {fraction}")
