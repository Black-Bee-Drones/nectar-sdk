"""Augmentation configuration builder."""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Union

import yaml

logger = logging.getLogger(__name__)


AUG_CONSERVATIVE = {
    "HorizontalFlip": {"p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.2, "contrast_limit": 0.2, "p": 0.5},
}

AUG_AGGRESSIVE = {
    "HorizontalFlip": {"p": 0.5},
    "VerticalFlip": {"p": 0.3},
    "Rotate": {"limit": 45, "p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.3, "contrast_limit": 0.3, "p": 0.5},
    "ShiftScaleRotate": {"shift_limit": 0.1, "scale_limit": 0.2, "rotate_limit": 15, "p": 0.5},
    "GaussianBlur": {"blur_limit": 3, "p": 0.3},
    "GaussNoise": {"var_limit": 10.0, "p": 0.3},
}

AUG_AERIAL = {
    "HorizontalFlip": {"p": 0.5},
    "VerticalFlip": {"p": 0.5},
    "Rotate": {"limit": 90, "p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.3, "contrast_limit": 0.3, "p": 0.5},
    "HueSaturationValue": {
        "hue_shift_limit": 20,
        "sat_shift_limit": 30,
        "val_shift_limit": 20,
        "p": 0.5,
    },
    "CLAHE": {"clip_limit": 2.0, "tile_grid_size": (8, 8), "p": 0.3},
}

AUG_INDUSTRIAL = {
    "HorizontalFlip": {"p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.2, "contrast_limit": 0.2, "p": 0.5},
    "GaussianBlur": {"blur_limit": 3, "p": 0.2},
    "MotionBlur": {"blur_limit": 3, "p": 0.2},
    "GaussNoise": {"var_limit": 10.0, "p": 0.2},
    "CLAHE": {"clip_limit": 2.0, "tile_grid_size": (8, 8), "p": 0.3},
}

PRESETS = {
    "conservative": AUG_CONSERVATIVE,
    "aggressive": AUG_AGGRESSIVE,
    "aerial": AUG_AERIAL,
    "industrial": AUG_INDUSTRIAL,
}


class AugmentationBuilder:
    """
    Build augmentation configurations from presets or custom configs.

    Parameters
    ----------
    preset : str, optional
        Preset name ("conservative", "aggressive", "aerial", "industrial").
    config : Dict, optional
        Custom augmentation configuration.
    """

    def __init__(self, preset: Optional[str] = None, config: Optional[Dict] = None):
        if preset and config:
            raise ValueError("Cannot specify both preset and config")
        if preset:
            if preset.lower() not in PRESETS:
                raise ValueError(f"Unknown preset: {preset}. Available: {list(PRESETS.keys())}")
            self.config = PRESETS[preset.lower()].copy()
            self.preset = preset.lower()
        elif config:
            self.config = config.copy()
            self.preset = None
        else:
            self.config = {}
            self.preset = None

    def add_transform(self, name: str, params: Dict) -> "AugmentationBuilder":
        """
        Add or update a transform.

        Parameters
        ----------
        name : str
            Transform name (Albumentations transform).
        params : Dict
            Transform parameters.

        Returns
        -------
        AugmentationBuilder
            Self for chaining.
        """
        self.config[name] = params
        return self

    def remove_transform(self, name: str) -> "AugmentationBuilder":
        """
        Remove a transform.

        Parameters
        ----------
        name : str
            Transform name to remove.

        Returns
        -------
        AugmentationBuilder
            Self for chaining.
        """
        if name in self.config:
            del self.config[name]
        return self

    def get_config(self) -> Dict:
        """
        Get augmentation configuration.

        Returns
        -------
        Dict
            Augmentation configuration dictionary.
        """
        return self.config.copy()

    def to_dict(self) -> Dict:
        """
        Convert to dictionary with metadata.

        Returns
        -------
        Dict
            Configuration dictionary with preset info.
        """
        result = {"transforms": self.config.copy()}
        if self.preset:
            result["preset"] = self.preset
        return result

    def to_yaml(self, path: Union[str, Path]) -> None:
        """
        Save configuration to YAML file.

        Parameters
        ----------
        path : str or Path
            Path to save YAML file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    def to_json(self, path: Union[str, Path]) -> None:
        """
        Save configuration to JSON file.

        Parameters
        ----------
        path : str or Path
            Path to save JSON file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "AugmentationBuilder":
        """
        Load configuration from YAML file.

        Parameters
        ----------
        path : str or Path
            Path to YAML file.

        Returns
        -------
        AugmentationBuilder
            New AugmentationBuilder instance.
        """
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)

        if "preset" in data:
            return cls(preset=data["preset"])
        elif "transforms" in data:
            return cls(config=data["transforms"])
        else:
            return cls(config=data)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "AugmentationBuilder":
        """
        Load configuration from JSON file.

        Parameters
        ----------
        path : str or Path
            Path to JSON file.

        Returns
        -------
        AugmentationBuilder
            New AugmentationBuilder instance.
        """
        path = Path(path)
        with open(path) as f:
            data = json.load(f)

        if "preset" in data:
            return cls(preset=data["preset"])
        elif "transforms" in data:
            return cls(config=data["transforms"])
        else:
            return cls(config=data)

    def validate(self) -> bool:
        """
        Validate augmentation configuration.

        Returns
        -------
        bool
            True if valid, False otherwise.
        """
        try:
            import albumentations as A

            transforms = []
            for name, params in self.config.items():
                if not hasattr(A, name):
                    logger.warning(f"Unknown transform: {name}")
                    return False
                transform_class = getattr(A, name)
                transforms.append(transform_class(**params))

            A.Compose(transforms)
            return True
        except ImportError:
            logger.warning("albumentations not installed, skipping validation")
            return True
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
