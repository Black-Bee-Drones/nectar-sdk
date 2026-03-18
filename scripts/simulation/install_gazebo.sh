#!/bin/bash
# =============================================================================
# install_gazebo.sh — Install Gazebo Harmonic + ArduPilot Gazebo plugin
#
# Sets up: Gazebo Harmonic, the ArduPilot Gazebo plugin (ArduPilotPlugin),
# and the ros_gz bridge for ROS2.
#
# Prerequisites:
#   - ROS2 Humble installed
#   - ArduPilot SITL installed (./scripts/simulation/install_sitl.sh)
#
# Usage:
#   ./scripts/simulation/install_gazebo.sh
# =============================================================================
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"

echo "╔══════════════════════════════════════════════════╗"
echo "║  Nectar SDK — Gazebo Simulation Installer        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  ROS distro: ${ROS_DISTRO}"
echo ""

# ── Install Gazebo Harmonic ─────────────────────────────────────────────────
echo "[INFO] Installing Gazebo Harmonic..."

sudo apt-get update
sudo apt-get install -y lsb-release wget gnupg

# Add Gazebo repository
sudo wget -q https://packages.osrfoundation.org/gazebo.gpg \
    -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

sudo apt-get update
sudo apt-get install -y gz-harmonic

# ── Install ros_gz bridge ──────────────────────────────────────────────────
# The apt-packaged ros_gz_bridge links against Ignition Transport 11 (Fortress)
# which is incompatible with Gazebo Harmonic's gz-transport 13.
# Install the apt packages (for deps), then rebuild ros_gz_bridge from source.
echo ""
echo "[INFO] Installing ros_gz (apt packages for dependencies)..."
sudo apt-get install -y \
    "ros-${ROS_DISTRO}-ros-gz" \
    "ros-${ROS_DISTRO}-ros-gz-bridge" \
    "ros-${ROS_DISTRO}-ros-gz-sim" \
    "ros-${ROS_DISTRO}-ros-gz-image"

echo ""
echo "[INFO] Rebuilding ros_gz_bridge from source for Gazebo Harmonic..."
ROS_GZ_SRC="${HOME}/ros2_ws/src/ros_gz"
if [ ! -d "${ROS_GZ_SRC}" ]; then
    git clone https://github.com/gazebosim/ros_gz.git -b "${ROS_DISTRO}" "${ROS_GZ_SRC}"
else
    echo "[INFO] ros_gz source already exists, pulling latest..."
    cd "${ROS_GZ_SRC}" && git pull || true
fi

cd "${HOME}/ros2_ws"
source "/opt/ros/${ROS_DISTRO}/setup.bash"
export GZ_VERSION=harmonic

# Build interfaces first, then bridge
colcon build --packages-up-to ros_gz_bridge --allow-overriding ros_gz_bridge ros_gz_interfaces --cmake-clean-cache
source install/setup.bash

# Verify the bridge links against gz-transport13
if ldd "${HOME}/ros2_ws/install/ros_gz_bridge/lib/ros_gz_bridge/parameter_bridge" 2>/dev/null | grep -q "libgz-transport13"; then
    echo "[OK] ros_gz_bridge rebuilt for Gazebo Harmonic (gz-transport13)"
else
    echo "[WARN] ros_gz_bridge may not be linked against gz-transport13"
fi

# ── Install ardupilot_gazebo (ArduPilotPlugin for Gazebo) ──────────────────
echo ""
echo "[INFO] Installing ardupilot_gazebo plugin..."

# Build dependencies
sudo apt-get install -y libgz-sim8-dev rapidjson-dev libopencv-dev

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

# ── Patch CMakeLists.txt for build compatibility ─────────────────────────────
# GStreamer is only needed for camera streaming, not SITL physics.
# Make it optional and guard the GstCameraPlugin target.
if grep -q "pkg_check_modules(GST REQUIRED" CMakeLists.txt; then
    echo "[INFO] Patching CMakeLists.txt: making GStreamer optional..."
    sed -i 's/pkg_check_modules(GST REQUIRED gstreamer-1.0 gstreamer-app-1.0)/pkg_check_modules(GST gstreamer-1.0 gstreamer-app-1.0)/' CMakeLists.txt
fi

if ! grep -q "if(GST_FOUND)" CMakeLists.txt; then
    echo "[INFO] Patching CMakeLists.txt: guarding GstCameraPlugin with if(GST_FOUND)..."
    sed -i '/^add_library(GstCameraPlugin/i if(GST_FOUND)' CMakeLists.txt
    # Insert endif() after the target_link_libraries closing paren for GstCameraPlugin
    sed -i '/target_link_libraries(GstCameraPlugin/,/^)/{/^)/a endif()
    }' CMakeLists.txt
    # Remove GstCameraPlugin from unconditional install list
    sed -i '/^  GstCameraPlugin$/d' CMakeLists.txt
fi

# ── Build ────────────────────────────────────────────────────────────────────
export GZ_VERSION=harmonic
rm -rf build
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
make -j$(nproc)

# Verify build
if [ ! -f "${ARDUPILOT_GAZEBO_DIR}/build/libArduPilotPlugin.so" ]; then
    echo "[ERROR] Build failed: libArduPilotPlugin.so not found"
    exit 1
fi
echo "[OK] ArduPilotPlugin built successfully"

# ── Environment ──────────────────────────────────────────────────────────────
echo ""
echo "[INFO] Configuring environment..."

MARKER="# ArduPilot Gazebo plugin (added by Nectar SDK)"
RESOURCE_LINE="export GZ_SIM_RESOURCE_PATH=\${HOME}/ardupilot_gazebo/models:\${HOME}/ardupilot_gazebo/worlds:\${GZ_SIM_RESOURCE_PATH:-}"
PLUGIN_LINE="export GZ_SIM_SYSTEM_PLUGIN_PATH=\${HOME}/ardupilot_gazebo/build:\${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"

# Remove old block if present, then write fresh
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
echo "║  Gazebo + ArduPilot plugin installed!            ║"
echo "║                                                  ║"
echo "║  Source your shell:                              ║"
echo "║    source ~/.bashrc                              ║"
echo "║                                                  ║"
echo "║  Test:                                           ║"
echo "║    make sim-start-gazebo   (terminal 1)          ║"
echo "║    make sim-gazebo         (terminal 2)          ║"
echo "╚══════════════════════════════════════════════════╝"
