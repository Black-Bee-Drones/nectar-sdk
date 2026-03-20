#!/bin/bash
# =============================================================================
# install_sitl.sh — Install ArduPilot SITL for Nectar SDK simulation
#
# One-time setup. Clones ArduPilot, installs prerequisites, and builds
# the ArduCopter SITL binary so sim_vehicle.py can be used headlessly.
#
# Usage:
#   ./scripts/simulation/install_sitl.sh [--dir <path>]
#
# Options:
#   --dir <path>   ArduPilot clone directory (default: ~/ardupilot)
# =============================================================================
set -euo pipefail

ARDUPILOT_DIR="${HOME}/ardupilot"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir) ARDUPILOT_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║  Nectar SDK — ArduPilot SITL Installer          ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Install directory: ${ARDUPILOT_DIR}"
echo ""

# ── Clone ArduPilot ─────────────────────────────────────────────────────────
if [ -d "${ARDUPILOT_DIR}" ]; then
    echo "[INFO] ArduPilot already exists at ${ARDUPILOT_DIR}, pulling latest..."
    cd "${ARDUPILOT_DIR}"
    git pull --recurse-submodules || true
    git submodule update --init --recursive
else
    echo "[INFO] Cloning ArduPilot..."
    git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "${ARDUPILOT_DIR}"
fi

cd "${ARDUPILOT_DIR}"

# ── Install prerequisites ───────────────────────────────────────────────────
echo ""
echo "[INFO] Installing ArduPilot prerequisites..."
Tools/environment_install/install-prereqs-ubuntu.sh -y

# Reload profile so sim_vehicle.py is in PATH
if [ -f "${HOME}/.profile" ]; then
    # shellcheck disable=SC1091
    . "${HOME}/.profile"
fi

# ── Build ArduCopter SITL ───────────────────────────────────────────────────
echo ""
echo "[INFO] Building ArduCopter SITL binary..."
./waf configure --board sitl
./waf copter

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ArduPilot SITL installed successfully!          ║"
echo "║                                                  ║"
echo "║  Test with:                                      ║"
echo "║    sim_vehicle.py -v ArduCopter --no-mavproxy    ║"
echo "╚══════════════════════════════════════════════════╝"
