#!/bin/bash
# =============================================================================
# Dev Entrypoint — runs inside the container on startup.
#
#  1. Sources ROS2 base + simulation overlay (set +u to avoid unbound vars)
#  2. Sets Gazebo + ArduPilot environment
#  3. Installs rosdep deps from mounted source
#  4. Builds SDK packages if needed (first run or NECTAR_REBUILD=1)
#  5. Sources SDK workspace overlay
#  6. Execs into CMD (default: bash)
# =============================================================================

WORKSPACE="/home/ros2_ws"
SRC_DIR="${WORKSPACE}/src/nectar-sdk"

# ---------- source ROS2 + simulation workspace ----------
# Use set +u because ROS2 setup.bash references unbound variables
set +u
# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"
# Source ros_gz overlay (built at image time into the workspace install dir)
if [ -f "${WORKSPACE}/install/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "${WORKSPACE}/install/setup.bash"
fi
set -eu

# ---------- Gazebo + ArduPilot environment ----------
export GZ_VERSION="${GZ_VERSION:-harmonic}"
export GZ_SIM_RESOURCE_PATH="/home/ardupilot_gazebo/models:/home/ardupilot_gazebo/worlds:${GZ_SIM_RESOURCE_PATH:-}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="/home/ardupilot_gazebo/build:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
export ARDUPILOT_DIR="${ARDUPILOT_DIR:-/home/ardupilot}"
export PATH="${ARDUPILOT_DIR}/Tools/autotest:${PATH}"

echo "[dev-entrypoint] ROS2 + Gazebo + ArduPilot environment ready."

# ---------- sanity check ----------
if [ ! -d "${SRC_DIR}/nectar" ]; then
    echo ""
    echo "ERROR: Source not found at ${SRC_DIR}/nectar"
    echo "       Make sure the host nectar-sdk directory is bind-mounted."
    echo ""
    exec "$@"
fi

# ---------- rosdep ----------
ROSDEP_STAMP="${WORKSPACE}/build/.rosdep_installed"
if [ ! -f "${ROSDEP_STAMP}" ] || [ "${NECTAR_ROSDEP:-0}" = "1" ]; then
    echo "[dev-entrypoint] Installing rosdep dependencies..."
    cd "${WORKSPACE}"
    rosdep install --from-paths src --ignore-src -r -y \
        --skip-keys="librealsense2" 2>/dev/null || true
    touch "${ROSDEP_STAMP}"
else
    echo "[dev-entrypoint] rosdep deps already installed (skip). Set NECTAR_ROSDEP=1 to re-run."
fi

# ---------- colcon build (SDK packages only) ----------
_needs_build=false

SDK_MARKER="${WORKSPACE}/build/nectar"
if [ ! -d "${SDK_MARKER}" ]; then
    echo "[dev-entrypoint] First run — building SDK packages..."
    _needs_build=true
fi

if [ "${NECTAR_REBUILD:-0}" = "1" ]; then
    echo "[dev-entrypoint] NECTAR_REBUILD=1 — rebuilding..."
    _needs_build=true
fi

if [ "$_needs_build" = true ]; then
    cd "${WORKSPACE}"
    colcon build --symlink-install \
        --packages-select nectar nectar_interfaces \
        --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        2>&1 | tail -20
    echo "[dev-entrypoint] SDK build complete."
fi

# ---------- re-source workspace (picks up SDK packages) ----------
set +u
if [ -f "${WORKSPACE}/install/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "${WORKSPACE}/install/setup.bash"
fi
set -eu

# ---------- exec CMD ----------
cd "${SRC_DIR}"
exec "$@"
