#!/bin/bash
# =============================================================================
# install_gazebo.sh — Install Gazebo + ros_gz + ArduPilot Gazebo plugin
#
#   Humble  → Gazebo Harmonic, ros_gz from source (apt binary links Fortress)
#   Jazzy   → Gazebo Harmonic, ros_gz from binary
#   Kilted  → Gazebo Ionic,    ros_gz from binary
#
# Prerequisites:
#   - ROS 2 installed
#   - ArduPilot SITL installed (./scripts/simulation/install_sitl.sh)
#
# Usage:
#   ./scripts/simulation/install_gazebo.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../lib/config.sh"

if [ -f "${CONFIG_FILE}" ]; then
    # shellcheck disable=SC1090
    source "${CONFIG_FILE}"
else
    echo "[WARN] config.sh not found at ${CONFIG_FILE}, using defaults"
    ROS_DISTRO="${ROS_DISTRO:-humble}"
    GZ_VERSION="${GZ_VERSION:-harmonic}"
    GZ_APT_PACKAGE="gz-harmonic"
    GZ_SIM_DEV_PACKAGE="libgz-sim8-dev"
    GZ_TRANSPORT_LIB="libgz-transport13"
    GZ_ROS_FROM_SOURCE=true
    WORKSPACE_DIR="${ROS2_WORKSPACE:-${HOME}/ros2_ws}"
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║  Nectar SDK — Gazebo Simulation Installer        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  ROS distro:       ${ROS_DISTRO}"
echo "  Gazebo version:   ${GZ_VERSION} (${GZ_APT_PACKAGE})"
echo "  ros_gz method:    $([ "${GZ_ROS_FROM_SOURCE}" = true ] && echo 'source' || echo 'binary')"
echo ""

# ── Install Gazebo ───────────────────────────────────────────────────────────
echo "[INFO] Installing ${GZ_APT_PACKAGE}..."

sudo apt-get update
sudo apt-get install -y lsb-release wget gnupg

sudo wget -q https://packages.osrfoundation.org/gazebo.gpg \
    -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

sudo apt-get update
sudo apt-get install -y "${GZ_APT_PACKAGE}"

# ── Install ros_gz bridge ───────────────────────────────────────────────────
if [ "${GZ_ROS_FROM_SOURCE}" = true ]; then
    echo ""
    echo "[INFO] Building ros_gz from source (required for ${ROS_DISTRO} + Gazebo ${GZ_VERSION})..."

    sudo apt-get install -y \
        "ros-${ROS_DISTRO}-ros-gz" \
        "ros-${ROS_DISTRO}-ros-gz-bridge" \
        "ros-${ROS_DISTRO}-ros-gz-sim" \
        "ros-${ROS_DISTRO}-ros-gz-image"

    ROS_GZ_SRC="${WORKSPACE_DIR}/src/ros_gz"
    if [ ! -d "${ROS_GZ_SRC}" ]; then
        git clone https://github.com/gazebosim/ros_gz.git -b "${ROS_DISTRO}" "${ROS_GZ_SRC}"
    else
        echo "[INFO] ros_gz source already exists, pulling latest..."
        cd "${ROS_GZ_SRC}" && git pull || true
    fi

    cd "${WORKSPACE_DIR}"
    set +u
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    set -u
    export GZ_VERSION="${GZ_VERSION}"

    if ! colcon build --help 2>&1 | grep -q "allow-overriding"; then
        pip install -q colcon-override-check 2>/dev/null || true
    fi
    colcon build --packages-up-to ros_gz_bridge \
        --allow-overriding ros_gz_bridge ros_gz_interfaces \
        --cmake-clean-cache
    set +u
    source install/setup.bash
    set -u

    if ldd "${WORKSPACE_DIR}/install/ros_gz_bridge/lib/ros_gz_bridge/parameter_bridge" 2>/dev/null \
        | grep -q "${GZ_TRANSPORT_LIB}"; then
        echo "[OK] ros_gz_bridge rebuilt for Gazebo ${GZ_VERSION} (${GZ_TRANSPORT_LIB})"
    else
        echo "[WARN] ros_gz_bridge may not be linked against ${GZ_TRANSPORT_LIB}"
    fi
else
    echo ""
    echo "[INFO] Installing ros_gz from binary (${ROS_DISTRO} ships compatible packages)..."

    sudo apt-get install -y \
        "ros-${ROS_DISTRO}-ros-gz" \
        "ros-${ROS_DISTRO}-ros-gz-bridge" \
        "ros-${ROS_DISTRO}-ros-gz-sim" \
        "ros-${ROS_DISTRO}-ros-gz-image"

    echo "[OK] ros_gz installed from binary"
fi

# ── Install ardupilot_gazebo (ArduPilotPlugin for Gazebo) ───────────────────
echo ""
echo "[INFO] Installing ardupilot_gazebo plugin..."

sudo apt-get install -y "${GZ_SIM_DEV_PACKAGE}" rapidjson-dev libopencv-dev

ARDUPILOT_GAZEBO_DIR="${HOME}/ardupilot_gazebo"

if [ -d "${ARDUPILOT_GAZEBO_DIR}" ]; then
    echo "[INFO] ardupilot_gazebo already exists, pulling latest..."
    cd "${ARDUPILOT_GAZEBO_DIR}"
    git checkout main 2>/dev/null || true
    git pull || true
else
    git clone https://github.com/ArduPilot/ardupilot_gazebo.git "${ARDUPILOT_GAZEBO_DIR}"
fi

cd "${ARDUPILOT_GAZEBO_DIR}"

# GStreamer is only needed for camera streaming, not SITL physics.
if grep -q "pkg_check_modules(GST REQUIRED" CMakeLists.txt; then
    echo "[INFO] Patching CMakeLists.txt: making GStreamer optional..."
    sed -i 's/pkg_check_modules(GST REQUIRED gstreamer-1.0 gstreamer-app-1.0)/pkg_check_modules(GST gstreamer-1.0 gstreamer-app-1.0)/' CMakeLists.txt
fi

if ! grep -q "if(GST_FOUND)" CMakeLists.txt; then
    echo "[INFO] Patching CMakeLists.txt: guarding GstCameraPlugin with if(GST_FOUND)..."
    sed -i '/^add_library(GstCameraPlugin/i if(GST_FOUND)' CMakeLists.txt
    sed -i '/target_link_libraries(GstCameraPlugin/,/^)/{/^)/a endif()
    }' CMakeLists.txt
    sed -i '/^  GstCameraPlugin$/d' CMakeLists.txt
fi

export GZ_VERSION="${GZ_VERSION}"
rm -rf build
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
make -j"$(nproc)"

if [ ! -f "${ARDUPILOT_GAZEBO_DIR}/build/libArduPilotPlugin.so" ]; then
    echo "[ERROR] Build failed: libArduPilotPlugin.so not found"
    exit 1
fi
echo "[OK] ArduPilotPlugin built successfully"

# ── Environment ─────────────────────────────────────────────────────────────
echo ""
echo "[INFO] Configuring environment..."

MARKER="# ArduPilot Gazebo plugin (added by Nectar SDK)"
RESOURCE_LINE="export GZ_SIM_RESOURCE_PATH=\${HOME}/ardupilot_gazebo/models:\${HOME}/ardupilot_gazebo/worlds:\${GZ_SIM_RESOURCE_PATH:-}"
PLUGIN_LINE="export GZ_SIM_SYSTEM_PLUGIN_PATH=\${HOME}/ardupilot_gazebo/build:\${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"

sed -i "/${MARKER}/,+2d" ~/.bashrc 2>/dev/null || true
{
    echo ""
    echo "${MARKER}"
    echo "${RESOURCE_LINE}"
    echo "${PLUGIN_LINE}"
} >> ~/.bashrc

echo "[OK] GZ_SIM_RESOURCE_PATH and GZ_SIM_SYSTEM_PLUGIN_PATH added to ~/.bashrc"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Gazebo ${GZ_VERSION} + ArduPilot plugin installed!"
echo "║                                                  ║"
echo "║  Source your shell:                              ║"
echo "║    source ~/.bashrc                              ║"
echo "║                                                  ║"
echo "║  Test:                                           ║"
echo "║    make sim-start-gazebo   (terminal 1)          ║"
echo "║    make sim-gazebo         (terminal 2)          ║"
echo "╚══════════════════════════════════════════════════╝"
