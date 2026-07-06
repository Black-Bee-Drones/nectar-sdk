from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "MavrosVisionRelay": "nectar.control.localization.vision_pose_bridge",
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_ATTRS})


if TYPE_CHECKING:
    from nectar.control.localization.vision_pose_bridge import MavrosVisionRelay


__all__ = ["MavrosVisionRelay"]
