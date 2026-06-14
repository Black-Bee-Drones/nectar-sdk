#!/bin/bash
# RealSense + Isaac ROS Visual SLAM.
#
# Usage:
#   ./run_docker.sh            set up + build (if needed) + enter the container
#   ./run_docker.sh -- <cmd>   run <cmd> inside an already-running container
#
# Inside the container, start the producer with the baked helper:
#   nectar-vslam
#
# Requirements: docker (non-root), git-lfs, NVIDIA Container Toolkit (Jetson).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"     # .../src/nectar-sdk
WORKSPACE_DIR="$(dirname "$(dirname "$SDK_DIR")")"  # .../ros2_ws (Isaac ROS workspace)

# shellcheck disable=SC1091
source "$SDK_DIR/scripts/lib/config.sh" >/dev/null 2>&1 || true
ISAAC_ROS_VERSION="${ISAAC_ROS_VERSION:-release-3.2}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-14}"

COMMON_DIR="$WORKSPACE_DIR/src/isaac_ros_common"
RUN_DEV="$COMMON_DIR/scripts/run_dev.sh"

# 1. Clone isaac_ros_common (provides run_dev.sh + prebuilt-base resolution).
if [[ ! -d "$COMMON_DIR" ]]; then
    echo "Cloning isaac_ros_common ($ISAAC_ROS_VERSION) into $COMMON_DIR ..."
    git clone -b "$ISAAC_ROS_VERSION" \
        https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common.git "$COMMON_DIR"
fi

# 2. Register the Nectar image layer (Dockerfile.nectar) with run_dev.sh.
#    build_image_layers.sh matches token "nectar" -> Dockerfile.nectar in the
#    search dir, layered on the prebuilt aarch64.ros2_humble base.
cat > "$COMMON_DIR/scripts/.isaac_ros_common-config" <<EOF
CONFIG_IMAGE_KEY=ros2_humble.nectar
CONFIG_DOCKER_SEARCH_DIRS=($SCRIPT_DIR)
CONFIG_CONTAINER_NAME_SUFFIX=nectar
EOF

# 3. Launch the dev container (builds/pulls on first run, attaches afterwards).
echo "Starting Isaac ROS dev container (ROS_DOMAIN_ID=$ROS_DOMAIN_ID) ..."
exec "$RUN_DEV" -d "$WORKSPACE_DIR" "$@"
