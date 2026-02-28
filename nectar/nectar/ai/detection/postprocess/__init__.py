"""
Post-processing module for detection results.

Strategies for merging, filtering, and processing detection results.
"""

from nectar.ai.detection.postprocess.base import BaseMergingStrategy
from nectar.ai.detection.postprocess.filtering import PerClassConfidenceFilter
from nectar.ai.detection.postprocess.nmm import NMMStrategy
from nectar.ai.detection.postprocess.nms import NMSStrategy
from nectar.ai.detection.postprocess.soft_nms import SoftNMSStrategy
from nectar.ai.detection.postprocess.wbf import WBFStrategy

__all__ = [
    "BaseMergingStrategy",
    "NMSStrategy",
    "SoftNMSStrategy",
    "WBFStrategy",
    "NMMStrategy",
    "PerClassConfidenceFilter",
]
