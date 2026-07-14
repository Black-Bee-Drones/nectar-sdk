#!/bin/bash
# =============================================================================
# install_px4_dds.sh — Set up the PX4 native uXRCE-DDS path (real hardware or sim)
#
# Installs only what the `px4_dds` drone needs to bridge PX4 <-> ROS 2 over
# uXRCE-DDS, WITHOUT pulling PX4-Autopilot / SITL / Gazebo:
#   - px4_msgs: ROS 2 message definitions (cloned into the workspace + built)
#   - Micro XRCE-DDS Agent: the PX4 <-> ROS 2 DDS bridge (built + installed)
#
# Used by:  make drone-px4-dds   (real hardware)
#           install_px4.sh --native   (alongside the SITL install for simulation)
#
# NOTE: the px4_msgs branch MUST match your PX4 firmware release (uORB topics are
# versioned). 'main' matches a 'main' PX4 checkout; for a release use the matching
# branch, e.g.  PX4_MSGS_BRANCH=release/1.15 make drone-px4-dds
#
# Agent tag must match the distro Fast-DDS / Fast-CDR ABI (override with AGENT_TAG):
#   humble  → v2.4.2  (FastCDR 1.x, fastrtps 2.x)
#   jazzy   → v2.4.3  (FastCDR 2.x, fastrtps 2.x)
#   kilted+ → v3.0.1  (FastCDR 2.x, fastdds 3.x; needs PX4 XRCE client ≥ v3)
# =============================================================================
set -euo pipefail

# Isolate our internal `make` calls (the agent) from any parent `make`.
unset MAKEFLAGS MAKEOVERRIDES MFLAGS MAKELEVEL 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_SRC="$(cd "${SCRIPT_DIR}/../../.." && pwd)"   # ros2_ws/src (parent of nectar-sdk)
WS_ROOT="$(dirname "${WS_SRC}")"                 # ros2_ws
PX4_MSGS_BRANCH="${PX4_MSGS_BRANCH:-}"           # empty = default branch (main)
AGENT_DIR="${AGENT_DIR:-${HOME}/Micro-XRCE-DDS-Agent}"

_as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

_agent_tag_for_distro() {
    case "${1}" in
        humble) echo "v2.4.2" ;;
        jazzy)  echo "v2.4.3" ;;
        *)      echo "v3.0.1" ;;
    esac
}

echo "[INFO] Setting up the PX4 native uXRCE-DDS path (px4_msgs + agent)..."

if [ -d "${WS_SRC}/px4_msgs" ]; then
    echo "[INFO] px4_msgs already present at ${WS_SRC}/px4_msgs"
else
    if [ -n "${PX4_MSGS_BRANCH}" ]; then
        echo "[INFO] Cloning px4_msgs (branch ${PX4_MSGS_BRANCH}) into ${WS_SRC}..."
        git clone -b "${PX4_MSGS_BRANCH}" https://github.com/PX4/px4_msgs.git "${WS_SRC}/px4_msgs"
    else
        echo "[INFO] Cloning px4_msgs into ${WS_SRC} (branch must match your PX4 release)..."
        git clone https://github.com/PX4/px4_msgs.git "${WS_SRC}/px4_msgs"
    fi
fi

# Source ROS so colcon and the agent's find_package(fastdds/fastrtps) resolve.
set +u
if [ -z "${ROS_DISTRO:-}" ]; then
    for d in kilted jazzy humble iron rolling; do
        [ -f "/opt/ros/$d/setup.bash" ] && { ROS_DISTRO="$d"; break; }
    done
fi
[ -n "${ROS_DISTRO:-}" ] && source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

AGENT_TAG="${AGENT_TAG:-$(_agent_tag_for_distro "${ROS_DISTRO}")}"

echo "[INFO] Building px4_msgs (required for drone 'px4_dds')..."
( cd "${WS_ROOT}" && colcon build --packages-select px4_msgs )

# Micro XRCE-DDS Agent: the PX4 <-> ROS 2 DDS bridge
if command -v MicroXRCEAgent >/dev/null 2>&1; then
    echo "[INFO] MicroXRCEAgent already installed"
else
    echo "[INFO] Building Micro-XRCE-DDS-Agent ${AGENT_TAG} (system Fast-DDS, ${ROS_DISTRO})..."
    # Drop any previous failed/wrong-tag tree so cmake sees the matching sources.
    rm -rf "${AGENT_DIR}"
    git clone -b "${AGENT_TAG}" --depth 1 \
        https://github.com/eProsima/Micro-XRCE-DDS-Agent.git "${AGENT_DIR}"
    mkdir -p "${AGENT_DIR}/build"
    # Reuse ROS's Fast-DDS/Fast-CDR instead of the bundled superbuild, whose
    # asio+OpenSSL build fails on recent distros (X509_check_host).
    ( cd "${AGENT_DIR}/build" && \
        cmake .. -DCMAKE_BUILD_TYPE=Release -DUAGENT_BUILD_EXECUTABLE=ON \
            -DUAGENT_USE_SYSTEM_FASTDDS=ON -DUAGENT_USE_SYSTEM_FASTCDR=ON && \
        make -j"$(nproc)" && \
        _as_root make install && \
        _as_root ldconfig )
fi

echo ""
echo "[OK] PX4 native uXRCE-DDS ready (px4_msgs built + MicroXRCEAgent installed)."
echo "     Real hardware: start the agent on the link your FCU uses, e.g."
echo "       MicroXRCEAgent serial --dev /dev/ttyUSB0 -b 921600     # serial"
echo "       MicroXRCEAgent udp4 -p 8888                            # UDP"
echo "     Then fly:  python3 nectar/nectar/examples/control/basic.py --drone px4_dds"
echo "     (Source the workspace first: source ${WS_ROOT}/install/setup.bash)"
