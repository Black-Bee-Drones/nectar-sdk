"""
Optical flow estimation with sparse and dense backends.

The estimator mirrors the model used by onboard flow chips (PMW3901,
ADNS-3080, MTF-01) and the ArduPilot EKF, exposed as a reusable
component for the Nectar SDK.

Pipeline
--------
1. Compute pixel displacement between consecutive frames using either
   Lucas-Kanade (sparse, Shi-Tomasi corners) or Farneback (dense).
2. Reduce the displacement field to a single mean vector ``(ux, uy)``
   in pixels per frame.
3. Divide by the inter-frame time ``dt`` to obtain px/s.
4. If the camera focal length ``focal_px`` is provided, convert to
   angular rate ``omega = (px/s) / focal_px`` in rad/s.
5. If altitude ``altitude_m`` is also provided, project to horizontal
   velocity ``v = omega * altitude_m`` in m/s.

Steps 4-5 are exactly the same math the ArduPilot driver applies to
the OPTICAL_FLOW MAVLink message (see ``drone/3-optical-flow.md``).

References
----------
OpenCV
    https://docs.opencv.org/4.x/dc/d6b/group__video__track.html
ArduPilot driver
    libraries/AP_OpticalFlow/AP_OpticalFlow_MAV.cpp

"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np


METHOD_LUCAS_KANADE = "lucas_kanade"
METHOD_FARNEBACK = "farneback"
_SUPPORTED_METHODS = (METHOD_LUCAS_KANADE, METHOD_FARNEBACK)


@dataclass
class OpticalFlowConfig:
    """
    Configuration for :class:`OpticalFlowEstimator`.

    Parameters
    ----------
    method : str
        Backend algorithm. One of ``"lucas_kanade"`` or ``"farneback"``.
    resize_to : tuple of (int, int), optional
        Downsample frames to ``(width, height)`` before processing for
        performance. ``None`` keeps the input resolution. The output
        flow is rescaled back to the input frame coordinates so the
        numeric result and overlay stay consistent.
    refresh_corners_below : int
        Lucas-Kanade only. Re-detect Shi-Tomasi corners when the number
        of successfully tracked points drops below this threshold.
        Lower values reduce flicker (corners are kept longer) at the
        cost of fewer arrows over time.
    max_corners : int
        Lucas-Kanade only. Maximum corners returned by
        ``cv2.goodFeaturesToTrack``.
    quality_level : float
        Lucas-Kanade only. Corner quality (0..1) passed to
        ``cv2.goodFeaturesToTrack``.
    min_distance : int
        Lucas-Kanade only. Minimum spacing between corners (pixels).
        Larger values spread corners out and reduce visual clutter.
    lk_win_size : int
        Lucas-Kanade only. Pyramid window size.
    lk_max_level : int
        Lucas-Kanade only. Pyramid max level (0 = no pyramid).
    lk_arrow_scale : float
        Lucas-Kanade only. Visual amplification for arrows so sub-pixel
        flow stays visible (does NOT affect numeric output).
    lk_min_draw_px : float
        Lucas-Kanade only. Vectors shorter than this (in raw pixels)
        are not drawn. Filters out tracking noise on still frames.
    ema_alpha : float
        Smoothing factor in [0, 1] applied to the displayed mean flow
        and quality. Higher = more responsive, lower = smoother.
        Numeric fields of :class:`OpticalFlowResult` are NOT smoothed
        (raw per-frame values), only the on-image text readout is.
    pyr_scale : float
        Farneback only. Pyramid scale (must be < 1).
    levels : int
        Farneback only. Number of pyramid levels.
    winsize : int
        Farneback only. Averaging window size.
    iterations : int
        Farneback only. Iterations per pyramid level.
    poly_n : int
        Farneback only. Pixel neighborhood for polynomial expansion.
    poly_sigma : float
        Farneback only. Gaussian std for polynomial smoothing.

    """

    method: str = METHOD_FARNEBACK
    resize_to: Optional[Tuple[int, int]] = None

    # Lucas-Kanade
    refresh_corners_below: int = 60
    max_corners: int = 180
    quality_level: float = 0.02
    min_distance: int = 14
    lk_win_size: int = 21
    lk_max_level: int = 3
    lk_arrow_scale: float = 4.0
    lk_min_draw_px: float = 0.4

    # Display smoothing
    ema_alpha: float = 0.35

    # Farneback
    pyr_scale: float = 0.5
    levels: int = 3
    winsize: int = 21
    iterations: int = 3
    poly_n: int = 5
    poly_sigma: float = 1.2

    def __post_init__(self) -> None:
        if self.method not in _SUPPORTED_METHODS:
            raise ValueError(
                f"method must be one of {_SUPPORTED_METHODS}, got {self.method!r}"
            )


@dataclass
class OpticalFlowResult:
    """
    Per-frame output of :meth:`OpticalFlowEstimator.process`.

    Attributes
    ----------
    method : str
        Backend that produced this result.
    dt_s : float
        Seconds elapsed since the previous processed frame.
    mean_flow_px : tuple of (float, float)
        Mean displacement ``(ux, uy)`` over the frame in pixels.
    mean_flow_px_per_s : tuple of (float, float)
        Mean displacement converted to pixels per second.
    angular_rate_rad_s : tuple of (float, float) or None
        Mean displacement converted to rad/s using ``focal_px``.
        ``None`` when no focal length was supplied.
    velocity_m_s : tuple of (float, float) or None
        Horizontal velocity in m/s assuming a downward-pointing camera.
        ``None`` unless both ``focal_px`` and ``altitude_m`` are given.
    quality : float
        Confidence in ``[0, 1]``. For Lucas-Kanade it is the fraction
        of points successfully tracked; for Farneback it is a ratio
        between the mean and the spread of the magnitude field.
    n_vectors : int
        Number of vectors that contributed to the mean.
    visualization : np.ndarray
        BGR overlay with arrows / HSV field plus a text readout.

    """

    method: str
    dt_s: float
    mean_flow_px: Tuple[float, float] = (0.0, 0.0)
    mean_flow_px_per_s: Tuple[float, float] = (0.0, 0.0)
    angular_rate_rad_s: Optional[Tuple[float, float]] = None
    velocity_m_s: Optional[Tuple[float, float]] = None
    quality: float = 0.0
    n_vectors: int = 0
    visualization: np.ndarray = field(default_factory=lambda: np.zeros((1, 1, 3), np.uint8))


class OpticalFlowEstimator:
    """
    Compute optical flow and convert it to angular rate / velocity.

    Parameters
    ----------
    config : OpticalFlowConfig, optional
        Configuration. Defaults to Farneback with sensible parameters.

    Examples
    --------
    >>> est = OpticalFlowEstimator(OpticalFlowConfig(method="lucas_kanade"))
    >>> result = est.process(frame_bgr, focal_px=500.0, altitude_m=1.5)
    >>> if result is not None:
    ...     print(result.velocity_m_s, result.quality)

    """

    def __init__(self, config: Optional[OpticalFlowConfig] = None) -> None:
        self._config = config or OpticalFlowConfig()
        self._prev_gray: Optional[np.ndarray] = None
        self._prev_points: Optional[np.ndarray] = None
        self._prev_timestamp: Optional[float] = None
        self._input_shape: Optional[Tuple[int, int]] = None  # (h, w) of input

        # Smoothed values used only for the on-image text readout.
        self._smooth_flow_px_s: Optional[Tuple[float, float]] = None
        self._smooth_quality: Optional[float] = None

    @property
    def config(self) -> OpticalFlowConfig:
        return self._config

    def reset(self) -> None:
        """Drop accumulated state so the next call starts fresh."""
        self._prev_gray = None
        self._prev_points = None
        self._prev_timestamp = None
        self._input_shape = None
        self._smooth_flow_px_s = None
        self._smooth_quality = None

    def process(
        self,
        frame_bgr: np.ndarray,
        *,
        timestamp_s: Optional[float] = None,
        focal_px: Optional[float] = None,
        altitude_m: Optional[float] = None,
    ) -> Optional[OpticalFlowResult]:
        """
        Compute optical flow for the current frame.

        Parameters
        ----------
        frame_bgr : np.ndarray
            Input BGR frame.
        timestamp_s : float, optional
            Capture timestamp in seconds. Defaults to ``time.monotonic()``.
        focal_px : float, optional
            Camera focal length in pixels. Required to compute
            ``angular_rate_rad_s`` and ``velocity_m_s``.
        altitude_m : float, optional
            Height above ground in meters. Required (together with
            ``focal_px``) to compute ``velocity_m_s``.

        Returns
        -------
        OpticalFlowResult or None
            ``None`` is returned on the very first call (no previous
            frame to compare against).

        """
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        self._input_shape = frame_bgr.shape[:2]

        processed = self._prepare(frame_bgr)
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

        now = float(timestamp_s) if timestamp_s is not None else time.monotonic()

        if self._prev_gray is None:
            self._prev_gray = gray
            self._prev_timestamp = now
            if self._config.method == METHOD_LUCAS_KANADE:
                self._prev_points = self._detect_corners(gray)
            return None

        prev_ts = self._prev_timestamp if self._prev_timestamp is not None else now
        dt = max(now - prev_ts, 1e-6)

        if self._config.method == METHOD_LUCAS_KANADE:
            mean_px, quality, n_vec, overlay = self._run_lucas_kanade(gray, processed)
        else:
            mean_px, quality, n_vec, overlay = self._run_farneback(gray, processed)

        overlay = self._upscale_overlay(overlay)
        mean_px_per_s = (mean_px[0] / dt, mean_px[1] / dt)

        angular = None
        velocity = None
        if focal_px is not None and focal_px > 0.0:
            angular = (mean_px_per_s[0] / float(focal_px), mean_px_per_s[1] / float(focal_px))
            if altitude_m is not None and altitude_m > 0.0:
                velocity = (angular[0] * float(altitude_m), angular[1] * float(altitude_m))

        smooth_px_s, smooth_quality = self._update_smoothing(mean_px_per_s, quality)
        smooth_angular = None
        smooth_velocity = None
        if focal_px is not None and focal_px > 0.0:
            smooth_angular = (
                smooth_px_s[0] / float(focal_px),
                smooth_px_s[1] / float(focal_px),
            )
            if altitude_m is not None and altitude_m > 0.0:
                smooth_velocity = (
                    smooth_angular[0] * float(altitude_m),
                    smooth_angular[1] * float(altitude_m),
                )

        overlay = self._draw_readout(
            overlay,
            self._config.method,
            smooth_px_s,
            smooth_angular,
            smooth_velocity,
            smooth_quality,
            n_vec,
            dt,
        )

        self._prev_gray = gray
        self._prev_timestamp = now

        return OpticalFlowResult(
            method=self._config.method,
            dt_s=dt,
            mean_flow_px=mean_px,
            mean_flow_px_per_s=mean_px_per_s,
            angular_rate_rad_s=angular,
            velocity_m_s=velocity,
            quality=quality,
            n_vectors=n_vec,
            visualization=overlay,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _prepare(self, frame_bgr: np.ndarray) -> np.ndarray:
        if self._config.resize_to is None:
            return frame_bgr
        w, h = self._config.resize_to
        if w <= 0 or h <= 0:
            return frame_bgr
        return cv2.resize(frame_bgr, (int(w), int(h)), interpolation=cv2.INTER_AREA)

    def _upscale_overlay(self, overlay: np.ndarray) -> np.ndarray:
        if self._input_shape is None or self._config.resize_to is None:
            return overlay
        h_in, w_in = self._input_shape
        if overlay.shape[0] == h_in and overlay.shape[1] == w_in:
            return overlay
        return cv2.resize(overlay, (w_in, h_in), interpolation=cv2.INTER_NEAREST)

    def _detect_corners(self, gray: np.ndarray) -> Optional[np.ndarray]:
        corners = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=self._config.max_corners,
            qualityLevel=self._config.quality_level,
            minDistance=self._config.min_distance,
            blockSize=7,
        )
        if corners is None or len(corners) == 0:
            return None
        # Sub-pixel refinement reduces tracking jitter frame to frame.
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03)
        cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)
        return corners

    def _run_lucas_kanade(
        self, gray: np.ndarray, frame_bgr: np.ndarray
    ) -> Tuple[Tuple[float, float], float, int, np.ndarray]:
        overlay = frame_bgr.copy()

        if self._prev_points is None or len(self._prev_points) < 4:
            self._prev_points = self._detect_corners(self._prev_gray)
            if self._prev_points is None:
                return (0.0, 0.0), 0.0, 0, overlay

        new_pts, status, _err = cv2.calcOpticalFlowPyrLK(
            self._prev_gray,
            gray,
            self._prev_points,
            None,
            winSize=(self._config.lk_win_size, self._config.lk_win_size),
            maxLevel=self._config.lk_max_level,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
        )

        if new_pts is None or status is None:
            self._prev_points = self._detect_corners(gray)
            return (0.0, 0.0), 0.0, 0, overlay

        status = status.reshape(-1).astype(bool)
        old_good = self._prev_points.reshape(-1, 2)[status]
        new_good = new_pts.reshape(-1, 2)[status]
        n_vec = int(old_good.shape[0])

        n_requested = int(self._prev_points.shape[0])
        quality = n_vec / n_requested if n_requested > 0 else 0.0

        if n_vec == 0:
            self._prev_points = self._detect_corners(gray)
            return (0.0, 0.0), 0.0, 0, overlay

        deltas = new_good - old_good
        # Robust mean: ignore outliers above 2x median magnitude
        mags = np.linalg.norm(deltas, axis=1)
        med = float(np.median(mags))
        mask = mags <= max(med * 2.0, 1e-3) if med > 1e-3 else np.ones(n_vec, bool)
        if mask.sum() < max(4, n_vec // 4):
            mask = np.ones(n_vec, bool)
        mean_px = (float(deltas[mask, 0].mean()), float(deltas[mask, 1].mean()))

        scale = max(1.0, float(self._config.lk_arrow_scale))
        min_draw = max(0.0, float(self._config.lk_min_draw_px))
        for (x_old, y_old), (dx, dy), m in zip(old_good, deltas, mags):
            cv2.circle(overlay, (int(x_old), int(y_old)), 2, (0, 200, 255), -1)
            if m < min_draw:
                continue
            x_end = int(x_old + dx * scale)
            y_end = int(y_old + dy * scale)
            cv2.arrowedLine(
                overlay,
                (int(x_old), int(y_old)),
                (x_end, y_end),
                (0, 255, 0),
                1,
                line_type=cv2.LINE_AA,
                tipLength=0.3,
            )

        if n_vec < self._config.refresh_corners_below:
            self._prev_points = self._detect_corners(gray)
        else:
            self._prev_points = new_good.reshape(-1, 1, 2).astype(np.float32)

        return mean_px, float(quality), n_vec, overlay

    def _run_farneback(
        self, gray: np.ndarray, frame_bgr: np.ndarray
    ) -> Tuple[Tuple[float, float], float, int, np.ndarray]:
        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray,
            gray,
            None,
            self._config.pyr_scale,
            self._config.levels,
            self._config.winsize,
            self._config.iterations,
            self._config.poly_n,
            self._config.poly_sigma,
            0,
        )

        ux = float(flow[..., 0].mean())
        uy = float(flow[..., 1].mean())
        mean_px = (ux, uy)

        mag = cv2.magnitude(flow[..., 0], flow[..., 1])
        mag_mean = float(mag.mean())
        mag_std = float(mag.std())
        # "Peaked vs flat" proxy: signal-to-spread, clipped to [0, 1].
        if mag_mean < 1e-6:
            quality = 0.0
        else:
            quality = float(np.clip(mag_mean / (mag_mean + mag_std + 1e-6), 0.0, 1.0))

        n_vec = int(flow.shape[0] * flow.shape[1])

        ang = np.arctan2(flow[..., 1], flow[..., 0])
        hsv = np.zeros_like(frame_bgr)
        hsv[..., 0] = ((ang + np.pi) * 180.0 / (2.0 * np.pi)).astype(np.uint8)
        hsv[..., 1] = 255
        mag_vis = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        hsv[..., 2] = mag_vis.astype(np.uint8)
        overlay = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return mean_px, quality, n_vec, overlay

    def _update_smoothing(
        self,
        flow_px_s: Tuple[float, float],
        quality: float,
    ) -> Tuple[Tuple[float, float], float]:
        alpha = float(np.clip(self._config.ema_alpha, 0.0, 1.0))
        if self._smooth_flow_px_s is None:
            self._smooth_flow_px_s = flow_px_s
        else:
            sx, sy = self._smooth_flow_px_s
            self._smooth_flow_px_s = (
                alpha * flow_px_s[0] + (1.0 - alpha) * sx,
                alpha * flow_px_s[1] + (1.0 - alpha) * sy,
            )
        if self._smooth_quality is None:
            self._smooth_quality = quality
        else:
            self._smooth_quality = alpha * quality + (1.0 - alpha) * self._smooth_quality
        return self._smooth_flow_px_s, self._smooth_quality

    @staticmethod
    def _draw_readout(
        frame: np.ndarray,
        method: str,
        mean_px_per_s: Tuple[float, float],
        angular: Optional[Tuple[float, float]],
        velocity: Optional[Tuple[float, float]],
        quality: float,
        n_vec: int,
        dt: float,
    ) -> np.ndarray:
        lines = [
            f"{method}   q: {quality:.2f}   n: {n_vec}   dt: {dt * 1000.0:.1f} ms",
            f"flow: ({mean_px_per_s[0]:+6.1f}, {mean_px_per_s[1]:+6.1f}) px/s",
        ]
        if angular is not None:
            lines.append(
                f"omega: ({angular[0]:+6.3f}, {angular[1]:+6.3f}) rad/s"
            )
        if velocity is not None:
            lines.append(
                f"v:     ({velocity[0]:+6.3f}, {velocity[1]:+6.3f}) m/s"
            )

        y = 22
        for text in lines:
            cv2.putText(
                frame,
                text,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                3,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                text,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            y += 20

        return frame
