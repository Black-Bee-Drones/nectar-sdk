"""
Post-processing module for detection results.

Strategies for merging, filtering, and processing detection results.
"""

from mirela_sdk.ai.detection.postprocess.base import BaseMergingStrategy
from mirela_sdk.ai.detection.postprocess.nmm import NMMStrategy
from mirela_sdk.ai.detection.postprocess.nms import NMSStrategy
from mirela_sdk.ai.detection.postprocess.soft_nms import SoftNMSStrategy
from mirela_sdk.ai.detection.postprocess.wbf import WBFStrategy

__all__ = [
    "BaseMergingStrategy",
    "NMSStrategy",
    "SoftNMSStrategy",
    "WBFStrategy",
    "NMMStrategy",
]
