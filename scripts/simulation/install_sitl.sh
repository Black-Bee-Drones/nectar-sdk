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

# ── Root handling ────────────────────────────────────────────────────────────
# ArduPilot's install-prereqs-ubuntu.sh hard-refuses to run as root (no bypass).
# When this script is invoked as root (e.g. a Docker build), re-run the whole
# installer as an unprivileged build user that has passwordless sudo (so its apt
# steps still work). Bare-metal (non-root) runs are unaffected. Choose the account
# with AP_BUILD_USER (default: nectar). The caller is responsible for exposing the
# resulting ~${AP_BUILD_USER}/ardupilot to the runtime user if they differ.
if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    AP_BUILD_USER="${AP_BUILD_USER:-nectar}"
    echo "[INFO] Running as root; ArduPilot must build as non-root -> build user '${AP_BUILD_USER}'."
    if ! command -v sudo >/dev/null 2>&1; then
        apt-get update && apt-get install -y --no-install-recommends sudo
    fi
    if ! id -u "${AP_BUILD_USER}" >/dev/null 2>&1; then
        useradd -m -s /bin/bash "${AP_BUILD_USER}"
    fi
    echo "${AP_BUILD_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${AP_BUILD_USER}-sim"
    chmod 0440 "/etc/sudoers.d/90-${AP_BUILD_USER}-sim"
    # Re-exec as the build user (its own HOME, intact args). exec replaces this
    # process; the non-root run skips this block.
    exec sudo -u "${AP_BUILD_USER}" -H bash "$0" "$@"
fi

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
