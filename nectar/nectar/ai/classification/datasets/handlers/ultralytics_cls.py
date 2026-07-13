"""Ultralytics built-in classification dataset handler."""

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Union

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler
from nectar.ai.paths import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)


def _resolve_dataset_root(data: Union[str, dict]) -> Path:
    """Resolve ImageFolder root from ``check_cls_dataset`` output."""
    if isinstance(data, str):
        return Path(data).resolve()

    if not isinstance(data, dict):
        raise ValueError(f"Unexpected check_cls_dataset result: {type(data)}")

    if "path" in data and data["path"] and str(data["path"]).lower() != "none":
        return Path(data["path"]).resolve()

    for key in ("train", "val", "test"):
        split_path = data.get(key)
        if split_path and str(split_path).lower() != "none":
            return Path(split_path).resolve().parent

    raise ValueError(f"Could not resolve dataset root from: {data}")


@contextmanager
def _nectar_ultralytics_datasets_dir(target: Path) -> Iterator[None]:
    """
    Temporarily point Ultralytics classification downloads at ``target``.

    Ultralytics keeps a global ``datasets_dir`` in
    ``~/.config/Ultralytics/settings.json``. That value is often left pointing
    at whatever project last called ``settings.update``. Worse, ``check_cls_dataset`` reads the module-level constant
    ``ultralytics.data.utils.DATASETS_DIR`` (frozen at import time), so updating
    settings alone is not enough — both must be overridden for the download.
    """
    try:
        from ultralytics import settings as ultralytics_settings
        from ultralytics.data import utils as ultralytics_data_utils
    except ImportError as e:
        raise ImportError("ultralytics is required. Install: pip install -e '.[ai]'") from e

    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)

    previous_setting = ultralytics_settings.get("datasets_dir")
    previous_const = getattr(ultralytics_data_utils, "DATASETS_DIR", None)

    ultralytics_settings.update({"datasets_dir": str(target)})
    ultralytics_data_utils.DATASETS_DIR = target
    logger.info("Ultralytics DATASETS_DIR → %s (was %s)", target, previous_const)
    try:
        yield
    finally:
        if previous_const is not None:
            ultralytics_data_utils.DATASETS_DIR = previous_const
        if previous_setting is not None:
            ultralytics_settings.update({"datasets_dir": previous_setting})
        logger.debug("Restored Ultralytics DATASETS_DIR → %s", previous_const or previous_setting)


class UltralyticsClsHandler(BaseDatasetHandler):
    """
    Download Ultralytics classification datasets (cifar10, mnist160, …).

    Uses ``ultralytics.data.utils.check_cls_dataset`` which auto-downloads on first
    use per the [Ultralytics classify dataset docs](https://docs.ultralytics.com/datasets/classify/).

    Downloads are forced into ``nectar/ai/data/ultralytics/`` (not the global
    Ultralytics ``datasets_dir``), then materialized under ``output_dir``.
    """

    # Shared cache for Ultralytics zip extracts, under the Nectar AI data tree.
    CACHE_DIR = DEFAULT_DATA_DIR / "ultralytics"

    def __init__(self, output_dir: str, verbose: bool = True):
        super().__init__(output_dir, verbose=verbose)

    def download(
        self,
        dataset: str = "mnist160",
        max_samples: Optional[int] = None,
        seed: int = 42,
        **kwargs,
    ) -> str:
        """
        Download or resolve a built-in Ultralytics classification dataset.

        Parameters
        ----------
        dataset : str
            Built-in name (``mnist160``, ``cifar10``, ``imagenette``, …).
        max_samples : int, optional
            If set, write a balanced subset with at most this many images per
            split (train/test) instead of the full dataset. Prefer this for
            smoke tests — CIFAR-10 is 60k images.
        seed : int
            RNG seed for subset sampling.
        """
        try:
            from ultralytics.data.utils import check_cls_dataset
        except ImportError as e:
            raise ImportError("ultralytics is required. Install: pip install -e '.[ai]'") from e

        with _nectar_ultralytics_datasets_dir(self.CACHE_DIR):
            data = check_cls_dataset(dataset)

        src_root = _resolve_dataset_root(data)
        if not src_root.exists():
            raise RuntimeError(f"Dataset root not found after download: {src_root}")

        dest = Path(self.output_dir).resolve()
        # Avoid nesting dest/dataset when the user already named the folder.
        if dest.name != dataset and not (dest / "train").is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            dest = dest / dataset

        if max_samples is not None:
            from nectar.ai.classification.datasets.format import subset_imagefolder

            # Subset directly from Ultralytics cache — do not copy the full
            # dataset (CIFAR-10 is 60k images) into the smoke output first.
            if dest.exists():
                shutil.rmtree(dest)
            subset_imagefolder(
                str(src_root),
                str(dest),
                max_train_samples=max_samples,
                max_eval_samples=max_samples,
                max_test_samples=max_samples,
                seed=seed,
            )
            self._print(f"Ultralytics '{dataset}' subset (max {max_samples}/split) → {dest}")
            logger.info("Wrote subset %s → %s", dataset, dest)
            return str(dest)

        if dest.resolve() != src_root.resolve():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src_root, dest)

        self._print(f"Ultralytics dataset '{dataset}' → {dest}")
        logger.info("Materialized Ultralytics dataset %s → %s", dataset, dest)
        return str(dest)

    def convert(self, format: str = "imagefolder", **kwargs) -> str:
        """Classification datasets are already ImageFolder — no conversion needed."""
        return str(self.output_dir)

    def download_and_convert(
        self,
        dataset: str = "mnist160",
        output_format: str = "imagefolder",
        max_samples: Optional[int] = None,
        **kwargs,
    ) -> str:
        return self.download(dataset=dataset, max_samples=max_samples, **kwargs)
