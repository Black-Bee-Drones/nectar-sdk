"""Temporarily pin Ultralytics DATASETS_DIR for nectar downloads."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


@contextmanager
def nectar_ultralytics_datasets_dir(target: Path) -> Iterator[None]:
    """
    Point Ultralytics downloads at ``target`` for the duration of the block.

    Ultralytics stores ``datasets_dir`` in ``~/.config/Ultralytics/settings.json``
    and freezes ``ultralytics.data.utils.DATASETS_DIR`` at import time. Both must
    be overridden or downloads land in whatever path another project last set.
    """
    try:
        from ultralytics import settings as ultralytics_settings
        from ultralytics.data import utils as ultralytics_data_utils
    except ImportError as e:
        raise ImportError("ultralytics is required. Install: pip install -e '.[ai]'") from e

    target = Path(target).resolve()
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
        logger.debug(
            "Restored Ultralytics DATASETS_DIR → %s",
            previous_const or previous_setting,
        )
