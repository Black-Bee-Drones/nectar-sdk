#!/bin/bash
# =============================================================================
# install_px4.sh — Install PX4 SITL (+ Gazebo) for Nectar SDK simulation
#
# One-time setup. Clones PX4-Autopilot, installs the PX4 toolchain and Gazebo
# simulation tools, and builds the PX4 SITL target. The first build fetches the
# PX4 Gazebo models (gz_x500, ...).
#
# Usage:
#   ./scripts/simulation/install_px4.sh [--dir <path>] [--native]
#
# Options:
#   --dir <path>   PX4-Autopilot clone directory (default: ~/PX4-Autopilot)
#   --native       Also set up the native uXRCE-DDS path: clone px4_msgs into the
#                  workspace and build the Micro XRCE-DDS Agent (for drone "px4_dds").
# =============================================================================
set -euo pipefail

# Isolate our internal `make` calls (px4_sitl, the agent) from the parent
unset MAKEFLAGS MAKEOVERRIDES MFLAGS MAKELEVEL 2>/dev/null || true

PX4_DIR="${HOME}/PX4-Autopilot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_SRC="$(cd "${SCRIPT_DIR}/../../.." && pwd)"  # ros2_ws/src (parent of nectar-sdk)
NECTAR_SIM_DIR="$(cd "${SCRIPT_DIR}/../../nectar/simulation" && pwd)"
WITH_NATIVE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir) PX4_DIR="$2"; shift 2 ;;
        --native) WITH_NATIVE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║  Nectar SDK — PX4 SITL Installer                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Install directory: ${PX4_DIR}"
echo ""

# ── Clone PX4-Autopilot ─────────────────────────────────────────────────────
if [ -d "${PX4_DIR}" ]; then
    echo "[INFO] PX4-Autopilot already exists at ${PX4_DIR}, pulling latest..."
    cd "${PX4_DIR}"
    git pull --recurse-submodules || true
    git submodule update --init --recursive
else
    echo "[INFO] Cloning PX4-Autopilot..."
    git clone --recurse-submodules https://github.com/PX4/PX4-Autopilot.git "${PX4_DIR}"
fi

cd "${PX4_DIR}"

# ── Install prerequisites (PX4 toolchain + Gazebo sim tools) ─────────────────
echo ""
echo "[INFO] Installing PX4 prerequisites (this also installs Gazebo)..."
bash ./Tools/setup/ubuntu.sh

# ── Build PX4 SITL ──────────────────────────────────────────────────────────
echo ""
echo "[INFO] Building PX4 SITL (first build fetches Gazebo models)..."
make px4_sitl

# ── Link Nectar SDK simulation assets into the PX4 tree ─────────────────────
# PX4 spawns models from ${PX4_GZ_MODELS}/<name>/model.sdf and starts worlds
# from ${PX4_GZ_WORLDS}/<world>.sdf. Symlinking keeps a single source of truth
# in nectar-sdk/nectar/simulation/ while making the assets discoverable by PX4.
echo ""
echo "[INFO] Linking Nectar simulation assets into the PX4 tree..."
PX4_MODELS_DIR="${PX4_DIR}/Tools/simulation/gz/models"
PX4_WORLDS_DIR="${PX4_DIR}/Tools/simulation/gz/worlds"

link_nectar_asset() {
    local src="$1"
    local dst="$2"
    if [ ! -e "${src}" ]; then
        echo "[WARN]   missing ${src} (skipped)"
        return
    fi
    if [ -L "${dst}" ] || [ -e "${dst}" ]; then
        rm -rf "${dst}"
    fi
    ln -s "${src}" "${dst}"
    echo "[OK]     ${dst} -> ${src}"
}

link_nectar_asset "${NECTAR_SIM_DIR}/models/x500_nectar"             "${PX4_MODELS_DIR}/x500_nectar"
link_nectar_asset "${NECTAR_SIM_DIR}/models/outdoor_field_scenery"   "${PX4_MODELS_DIR}/outdoor_field_scenery"
link_nectar_asset "${NECTAR_SIM_DIR}/worlds/outdoor_field_px4.sdf"   "${PX4_WORLDS_DIR}/outdoor_field_px4.sdf"

# ── Native uXRCE-DDS path (optional) ────────────────────────────────────────
# Shares the same implementation as `make drone-px4-dds` (px4_msgs + agent),
# kept in a single script so the real-hardware and simulation paths never drift.
if [ "${WITH_NATIVE}" = true ]; then
    echo ""
    bash "${SCRIPT_DIR}/install_px4_dds.sh"
    echo ""
    echo "[INFO] For PX4 SITL over DDS, run (3 terminals):"
    echo "         make sim-start  FIRMWARE=px4 ENV=outdoor"
    echo "         make sim-bridge FIRMWARE=px4 ENV=outdoor PROTOCOL=dds   # MicroXRCEAgent"
    echo "         python3 nectar/nectar/examples/control/basic.py --drone px4_dds --env outdoor"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  PX4 SITL installed successfully!                ║"
echo "║                                                  ║"
echo "║  Test with (from the SDK root):                  ║"
echo "║    make sim-start  FIRMWARE=px4 ENV=outdoor      ║"
echo "║    make sim-bridge FIRMWARE=px4 ENV=outdoor      ║"
echo "╚══════════════════════════════════════════════════╝"
