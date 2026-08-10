"""ENU/FLU <-> NED/FRD helpers shared by the vision pose/speed bridges.

See ``nectar/control/localization/README.md`` for VSLAM conventions and FCU fusion.
"""

import math
from typing import List, Sequence, Tuple

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]

# ENU -> NED for a 6x6 pose covariance (MAVROS ``ftf::transform_static_frame``):
# signed permutation collapsing ``P (D C D) Pᵀ``.
_ENU_NED_SRC = (1, 0, 2, 4, 3, 5)
_ENU_NED_SIGN = (1.0, 1.0, -1.0, 1.0, 1.0, -1.0)


def rotate_by_quaternion(vec: Vec3, quat: Quat) -> Vec3:
    """Rotate ``vec`` by unit quaternion ``quat`` ``(x, y, z, w)`` — ``q v q*``."""
    vx, vy, vz = vec
    qx, qy, qz, qw = quat

    cx = qy * vz - qz * vy
    cy = qz * vx - qx * vz
    cz = qx * vy - qy * vx

    ccx = qy * cz - qz * cy
    ccy = qz * cx - qx * cz
    ccz = qx * cy - qy * cx

    return (
        vx + 2.0 * (qw * cx + ccx),
        vy + 2.0 * (qw * cy + ccy),
        vz + 2.0 * (qw * cz + ccz),
    )


def enu_to_ned(vec: Vec3) -> Vec3:
    """Swap an ENU (or FLU) vector to NED (or FRD). Involution: NED->ENU is the same."""
    x, y, z = vec
    return (y, x, -z)


def yaw_enu_to_ned(yaw: float) -> float:
    """ENU yaw (0=East, CCW) <-> NED yaw (0=North). Involution."""
    return (math.pi / 2.0) - yaw


def euler_enu_to_ned(roll: float, pitch: float, yaw: float) -> Vec3:
    """ENU/FLU RPY -> NED/FRD. Closed form of the MAVROS quaternion composition."""
    return (roll, -pitch, yaw_enu_to_ned(yaw))


def body_velocity_to_ned(linear: Vec3, orientation: Quat) -> Vec3:
    """Body-frame linear velocity -> FCU NED using the sample's attitude."""
    return enu_to_ned(rotate_by_quaternion(linear, orientation))


def pose_covariance_enu_to_ned(cov: Sequence[float]) -> List[float]:
    """Rotate a row-major 6x6 ``(x, y, z, roll, pitch, yaw)`` covariance to NED."""
    out = [0.0] * 36
    for i in range(6):
        for j in range(6):
            out[i * 6 + j] = (
                _ENU_NED_SIGN[i]
                * _ENU_NED_SIGN[j]
                * float(cov[_ENU_NED_SRC[i] * 6 + _ENU_NED_SRC[j]])
            )
    return out


def pose_variance_diagonal_enu_to_ned(cov: Sequence[float]) -> Tuple[Vec3, Vec3]:
    """ENU 6x6 diagonal variances -> NED ``(position_var, orientation_var)``.

    Matches the diagonal of :func:`pose_covariance_enu_to_ned` (signs square to 1).
    Used by PX4 ``VehicleOdometry``, which only carries per-axis variances.
    """
    ned = pose_covariance_enu_to_ned(cov)
    position_var = (ned[0], ned[7], ned[14])
    orientation_var = (ned[21], ned[28], ned[35])
    return position_var, orientation_var


def covariance_urt_to_mavlink(cov: Sequence[float]) -> List[float]:
    """Pack a row-major 6x6 into MAVLink's 21-float upper triangle (diagonal at 0,6,11,15,18,20)."""
    return [float(cov[y * 6 + x]) for x in range(6) for y in range(x, 6)]
