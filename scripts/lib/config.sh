#!/bin/bash

# Project
PROJECT_REPO="git@github.com:Black-Bee-Drones/mirela-sdk.git"
PROJECT_DIR_NAME="mirela-sdk"
ROS2_PKG_NAME="mirela_sdk"
INTERFACES_PKG_NAME="mirela_interfaces"
DOCKER_IMAGE_PREFIX="mirela-sdk"

ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_DOMAIN_ID="14"

# PyTorch
TORCH_VARIANT="${TORCH_VARIANT:-auto}"
TORCH_VERSION="${TORCH_VERSION:-}"
TORCHVISION_VERSION="${TORCHVISION_VERSION:-}"

TORCH_CONSTRAINTS_FILE="/tmp/mirela-torch-constraints.txt"
TORCH_INDEX_FILE="/tmp/mirela-torch-index.txt"

# RealSense — versions depend on ROS distro and camera target.
# Override with env vars: LIBREALSENSE_VERSION, REALSENSE_ROS_TAG
# T265 requires: LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1
if [[ "$ROS_DISTRO" == "humble" || "$ROS_DISTRO" == "iron" ]]; then
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.55.1}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.55.1}"
elif [[ "$ROS_DISTRO" == "jazzy" ]]; then
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.56.5}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.56.4}"
elif [[ "$ROS_DISTRO" == "kilted" ]]; then
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.56.5}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.57.2}"
else
    LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.55.1}"
    REALSENSE_ROS_TAG="${REALSENSE_ROS_TAG:-4.55.1}"
fi

# System apt packages
SYSTEM_PACKAGES=(
    git curl wget software-properties-common
    python3-pip python3-dev python3-venv
    build-essential cmake pkg-config
    python3-colcon-common-extensions python3-rosdep
    libboost-python-dev
    tmux fswebcam v4l-utils
    lsb-release gnupg2
    libssl-dev libusb-1.0-0-dev
)

# ROS2 apt packages
ROS2_PACKAGES=(
    "ros-${ROS_DISTRO}-desktop-full"
    "ros-${ROS_DISTRO}-mavros"
    "ros-${ROS_DISTRO}-mavros-extras"
    "ros-${ROS_DISTRO}-tf-transformations"
    "ros-${ROS_DISTRO}-ament-cmake"
    "ros-${ROS_DISTRO}-vision-opencv"
    "ros-${ROS_DISTRO}-cv-bridge"
    "ros-${ROS_DISTRO}-image-geometry"
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
