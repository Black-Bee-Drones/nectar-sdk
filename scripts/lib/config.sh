#!/bin/bash

# Project
PROJECT_REPO="git@github.com:Black-Bee-Drones/nectar-sdk.git"
PROJECT_DIR_NAME="nectar-sdk"
ROS2_PKG_NAME="nectar"
INTERFACES_PKG_NAME="nectar_interfaces"
DOCKER_IMAGE_PREFIX="nectar-sdk"

ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-14}"

# Isaac ROS (Jetson VSLAM container, docker/isaac_vslam/).
# release-3.2 = Humble / JetPack 6.x, built via isaac_ros_common/run_dev.sh.
ISAAC_ROS_VERSION="${ISAAC_ROS_VERSION:-release-3.2}"

# PyTorch - Override with env vars; if you bump
# TORCH_VERSION, set a matching TORCHVISION_VERSION too.
TORCH_VARIANT="${TORCH_VARIANT:-auto}"
TORCH_VERSION="${TORCH_VERSION:-2.9.1}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-0.24.1}"

export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-600}"

TORCH_CONSTRAINTS_FILE="/tmp/nectar-torch-constraints.txt"
TORCH_INDEX_FILE="/tmp/nectar-torch-index.txt"

# RealSense — versions depend on ROS distro and camera target.
# Override with env vars: LIBREALSENSE_VERSION, REALSENSE_ROS_TAG
# T265 requires: LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 (Humble only)
if [[ "$ROS_DISTRO" == "humble" ]]; then
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.55.1}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.55.1}"
elif [[ "$ROS_DISTRO" == "jazzy" ]]; then
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.56.5}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.56.4}"
elif [[ "$ROS_DISTRO" == "kilted" ]]; then
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.57.6}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.57.2}"
else
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.55.1}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.55.1}"
fi

# Gazebo — version and ros_gz install method depend on ROS distro.
# Humble needs ros_gz built from source (apt binary links against Fortress).
# Jazzy/Kilted ship ros_gz binaries that match their default Gazebo version.
if [[ "$ROS_DISTRO" == "humble" ]]; then
    GZ_VERSION="${GZ_VERSION:-harmonic}"
    GZ_APT_PACKAGE="gz-harmonic"
    GZ_SIM_DEV_PACKAGE="libgz-sim8-dev"
    GZ_TRANSPORT_LIB="libgz-transport13"
    GZ_ROS_FROM_SOURCE=true
elif [[ "$ROS_DISTRO" == "jazzy" ]]; then
    GZ_VERSION="${GZ_VERSION:-harmonic}"
    GZ_APT_PACKAGE="gz-harmonic"
    GZ_SIM_DEV_PACKAGE="libgz-sim8-dev"
    GZ_TRANSPORT_LIB="libgz-transport13"
    GZ_ROS_FROM_SOURCE=false
elif [[ "$ROS_DISTRO" == "kilted" ]]; then
    GZ_VERSION="${GZ_VERSION:-ionic}"
    GZ_APT_PACKAGE="gz-ionic"
    GZ_SIM_DEV_PACKAGE="libgz-sim9-dev"
    GZ_TRANSPORT_LIB="libgz-transport14"
    GZ_ROS_FROM_SOURCE=false
else
    GZ_VERSION="${GZ_VERSION:-harmonic}"
    GZ_APT_PACKAGE="gz-harmonic"
    GZ_SIM_DEV_PACKAGE="libgz-sim8-dev"
    GZ_TRANSPORT_LIB="libgz-transport13"
    GZ_ROS_FROM_SOURCE=true
fi

# System apt packages
SYSTEM_PACKAGES=(
    git git-lfs curl wget software-properties-common
    python3-pip python3-dev python3-venv
    build-essential cmake pkg-config rsync
    python3-colcon-common-extensions python3-rosdep
    libboost-python-dev
    tmux fswebcam v4l-utils
    lsb-release gnupg2
    libssl-dev libusb-1.0-0-dev
)

# ROS2 apt packages (core, distro-agnostic). MAVROS is NOT here: it is specific
# to the MAVROS control backend and is installed on demand via `make drone-mavros`
# (scripts/lib/drones.sh). Keep this list to what every install needs.
ROS2_PACKAGES=(
    "ros-${ROS_DISTRO}-ros-base"
    "ros-${ROS_DISTRO}-rviz2"
    "ros-${ROS_DISTRO}-tf-transformations"
    "ros-${ROS_DISTRO}-ament-cmake"
    "ros-${ROS_DISTRO}-vision-opencv"
    "ros-${ROS_DISTRO}-cv-bridge"
    "ros-${ROS_DISTRO}-image-geometry"
)

# Crazyflie / Crazyswarm2 apt packages
CRAZYFLIE_PACKAGES=(
    "ros-${ROS_DISTRO}-crazyflie"
    "ros-${ROS_DISTRO}-crazyflie-interfaces"
)

# Crazyswarm2 source fallback
CRAZYSWARM2_REPO="${CRAZYSWARM2_REPO:-https://github.com/IMRCLab/crazyswarm2}"
CRAZYSWARM2_REF="${CRAZYSWARM2_REF:-}"

# Bebop driver (jeremyfix ros2_bebop_driver + ros2_parrot_arsdk, built from source).
# apt deps required to build/run the driver.
BEBOP_APT_PACKAGES=(
    "ros-${ROS_DISTRO}-camera-info-manager"
    "ros-${ROS_DISTRO}-image-transport"
    "ros-${ROS_DISTRO}-cv-bridge"
    libavdevice-dev
    libavahi-client-dev
    python-is-python3
)

# arsdk must be built before the driver that links against it.
BEBOP_REPOS=(
    "ros2_parrot_arsdk=https://github.com/jeremyfix/ros2_parrot_arsdk.git"
    "ros2_bebop_driver=https://github.com/jeremyfix/ros2_bebop_driver.git"
)

# Qt6/PySide6 system dependencies
GUI_SYSTEM_PACKAGES=(
    libxcb-cursor0 libxcb-shape0 libxcb-icccm4 libxcb-image0
    libxcb-keysyms1 libxcb-render-util0 libxkbcommon-x11-0
    libegl1 libgl1
)

# RealSense system dependencies
REALSENSE_SYSTEM_PACKAGES=(
    libssl-dev libusb-1.0-0-dev pkg-config
    libgtk-3-dev libglfw3-dev
    libgl1-mesa-dev libglu1-mesa-dev
    python3 python3-dev
)

REALSENSE_CUDA_PACKAGES=(
    libgles2-mesa-dev libegl1-mesa-dev
)

# Path detection
if [[ -n "${BASH_SOURCE[0]}" ]]; then
    _CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    _SCRIPTS_DIR="$(dirname "$_CONFIG_DIR")"
    PROJECT_DIR="$(dirname "$_SCRIPTS_DIR")"
fi

# Detect workspace: walk up from PROJECT_DIR until we find a colcon workspace
# Expected: <WORKSPACE>/src/<project>/scripts/lib/config.sh
detect_workspace() {
    local dir="$PROJECT_DIR"
    local candidate="$(dirname "$(dirname "$dir")")"
    if [ -d "$candidate/src" ]; then
        echo "$candidate"
        return
    fi
    echo "${ROS2_WORKSPACE:-$HOME/ros2_ws}"
}

WORKSPACE_DIR="$(detect_workspace)"

PKG_DIR="${PROJECT_DIR}/${ROS2_PKG_NAME}"

# Shared workspace virtual environment. One venv per colcon
# workspace, reused by the SDK and any sibling project (e.g. competition code).
# Override with NECTAR_VENV=/custom/path; an already-active VIRTUAL_ENV wins.
NECTAR_VENV="${NECTAR_VENV:-${VIRTUAL_ENV:-${WORKSPACE_DIR}/.venv}}"
