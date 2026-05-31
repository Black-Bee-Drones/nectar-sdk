"""
Optical flow algorithms for translation/velocity estimation.

This module mirrors the model used by onboard flow sensors (PMW3901,
PX4FLOW, MTF-01) and the ArduPilot EKF:

    pixel displacement (px/frame)
    -> angular rate omega = (px/frame) / dt * (1 / focal_px)
    -> horizontal velocity v = omega * altitude_m

See ``drone/3-optical-flow.md`` for the derivation.

Classes
-------
OpticalFlowEstimator
    High-level estimator with two backends (Lucas-Kanade sparse,
    Farneback dense). Returns flow rate in px/s, rad/s and m/s plus
    an annotated visualization frame.
OpticalFlowConfig
    Dataclass holding all tunables (algorithm choice, OpenCV parameters,
    optional downsampling).
OpticalFlowResult
    Dataclass with per-frame numeric output and the visualization.
"""

from nectar.vision.algorithms.flow.optical_flow import (
    OpticalFlowConfig,
    OpticalFlowEstimator,
    OpticalFlowResult,
)

__all__ = [
    "OpticalFlowConfig",
    "OpticalFlowEstimator",
    "OpticalFlowResult",
]
