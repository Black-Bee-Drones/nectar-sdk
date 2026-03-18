#!/bin/bash
# =============================================================================
# start_sitl.sh — Start ArduPilot SITL for Nectar SDK
#
# Launches ArduCopter SITL with sensible defaults for MAVROS connection.
# MAVROS connects on tcp://127.0.0.1:5760 (SERIAL0, default TCP server).
#
# Usage:
#   ./scripts/simulation/start_sitl.sh [options]
#
# Options:
#   --dir <path>        ArduPilot directory (default: ~/ardupilot)
#   --vehicle <type>    Vehicle type (default: ArduCopter)
#   --location <name>   Predefined location (default: none, uses SITL default)
#   --speedup <N>       Simulation speed multiplier (default: 1)
#   --gazebo            Use Gazebo for physics (--model json). Start Gazebo
#                       separately with: ros2 launch nectar sitl_gazebo.launch.py
#   --indoor            Load indoor.parm (no GPS, EKF3 ExternalNav). Implies --gazebo.
#   --map               Launch with MAVProxy + map (requires display)
#   --extra <args>      Extra arguments passed to the binary or sim_vehicle.py
#
# Examples:
#   ./scripts/simulation/start_sitl.sh
#   ./scripts/simulation/start_sitl.sh --gazebo
#   ./scripts/simulation/start_sitl.sh --location KSFO
#   ./scripts/simulation/start_sitl.sh --speedup 2
#   ./scripts/simulation/start_sitl.sh --indoor
#   ./scripts/simulation/start_sitl.sh --map
# =============================================================================
set -euo pipefail

ARDUPILOT_DIR="${ARDUPILOT_DIR:-${HOME}/ardupilot}"
VEHICLE="ArduCopter"
LOCATION=""
SPEEDUP="1"
USE_MAP=false
USE_GAZEBO=false
USE_INDOOR=false
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)      ARDUPILOT_DIR="$2"; shift 2 ;;
        --vehicle)  VEHICLE="$2"; shift 2 ;;
        --location) LOCATION="$2"; shift 2 ;;
        --speedup)  SPEEDUP="$2"; shift 2 ;;
        --gazebo)   USE_GAZEBO=true; shift ;;
        --indoor)   USE_INDOOR=true; USE_GAZEBO=true; shift ;;
        --map)      USE_MAP=true; shift ;;
        --extra)    EXTRA_ARGS="$2"; shift 2 ;;
        -h|--help)
            head -n 27 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)          echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Validate ────────────────────────────────────────────────────────────────
if [ ! -d "${ARDUPILOT_DIR}" ]; then
    echo "[ERROR] ArduPilot not found at ${ARDUPILOT_DIR}"
    echo "        Run: ./scripts/simulation/install_sitl.sh"
    exit 1
fi

BINARY="${ARDUPILOT_DIR}/build/sitl/bin/arducopter"
if [ ! -f "${BINARY}" ]; then
    echo "[ERROR] ArduCopter binary not found at ${BINARY}"
    echo "        Run: ./scripts/simulation/install_sitl.sh"
    exit 1
fi

DEFAULTS="${ARDUPILOT_DIR}/Tools/autotest/default_params/copter.parm"
if [ ! -f "${DEFAULTS}" ]; then
    echo "[ERROR] Default params not found at ${DEFAULTS}"
    exit 1
fi

# Model: "+" for internal physics, "json" for Gazebo physics
MODEL="+"
if [ "${USE_GAZEBO}" = true ]; then
    MODEL="json"
fi

# Resolve param file paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

GAZEBO_PARM=""
if [ "${USE_GAZEBO}" = true ]; then
    GAZEBO_PARM="${PROJECT_DIR}/nectar/simulation/params/gazebo.parm"
    if [ ! -f "${GAZEBO_PARM}" ]; then
        echo "[ERROR] Gazebo param file not found at ${GAZEBO_PARM}"
        exit 1
    fi
fi

INDOOR_PARM=""
if [ "${USE_INDOOR}" = true ]; then
    INDOOR_PARM="${PROJECT_DIR}/nectar/simulation/params/indoor.parm"
    if [ ! -f "${INDOOR_PARM}" ]; then
        echo "[ERROR] Indoor param file not found at ${INDOOR_PARM}"
        exit 1
    fi
fi

# ── Launch ──────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║  Nectar SDK — ArduPilot SITL                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Vehicle:  ${VEHICLE}"
echo "  Model:    ${MODEL}"
echo "  Indoor:   ${USE_INDOOR}"
echo "  Location: ${LOCATION:-default}"
echo "  Speedup:  ${SPEEDUP}x"
echo "  MAVROS:   tcp://127.0.0.1:5760"
echo ""

if [ "${USE_GAZEBO}" = true ]; then
    echo "  Gazebo mode — launch Gazebo + MAVROS separately:"
    echo "    ros2 launch nectar sitl_gazebo.launch.py"
else
    echo "  Connect MAVROS with:"
    echo "    ros2 launch nectar sitl.launch.py"
    echo "    # or: ros2 launch mavros apm.launch fcu_url:=tcp://127.0.0.1:5760"
fi
echo ""

if [ "${USE_MAP}" = true ]; then
    # With MAVProxy: use sim_vehicle.py (requires display for xterm + map)
    export PATH="${ARDUPILOT_DIR}/Tools/autotest:${PATH}"
    if ! command -v sim_vehicle.py &>/dev/null; then
        echo "[ERROR] sim_vehicle.py not found in PATH"
        exit 1
    fi

    CMD="sim_vehicle.py -v ${VEHICLE}"
    [ -n "${LOCATION}" ] && CMD="${CMD} -L ${LOCATION}"
    [ "${SPEEDUP}" != "1" ] && CMD="${CMD} --speedup ${SPEEDUP}"
    [ -n "${EXTRA_ARGS}" ] && CMD="${CMD} ${EXTRA_ARGS}"

    echo "  Mode:     MAVProxy (with map)"
    echo "  Command:  ${CMD}"
    echo ""
    cd "${ARDUPILOT_DIR}"
    eval "${CMD}"
else
    # Without MAVProxy: run the binary directly in the current terminal.
    # SERIAL0 defaults to a TCP server on port 5760.
    # Build defaults: base copter params + optional gazebo/indoor params (comma-separated)
    ALL_DEFAULTS="${DEFAULTS}"
    [ -n "${GAZEBO_PARM}" ] && ALL_DEFAULTS="${ALL_DEFAULTS},${GAZEBO_PARM}"
    [ -n "${INDOOR_PARM}" ] && ALL_DEFAULTS="${ALL_DEFAULTS},${INDOOR_PARM}"

    CMD="${BINARY} --model ${MODEL} --speedup ${SPEEDUP}"
    CMD="${CMD} --defaults ${ALL_DEFAULTS}"
    # Wipe eeprom in Gazebo mode so --defaults (rangefinder, indoor, etc.) take effect
    [ "${USE_GAZEBO}" = true ] && CMD="${CMD} -w"
    CMD="${CMD} --sim-address=127.0.0.1 -I0"

    if [ -n "${LOCATION}" ]; then
        # Look up lat/lon from ArduPilot's locations.txt
        LOCATIONS_FILE="${ARDUPILOT_DIR}/Tools/autotest/locations.txt"
        if [ -f "${LOCATIONS_FILE}" ]; then
            LOC_LINE=$(grep "^${LOCATION}=" "${LOCATIONS_FILE}" || true)
            if [ -n "${LOC_LINE}" ]; then
                HOME_POS=$(echo "${LOC_LINE}" | cut -d= -f2)
                CMD="${CMD} --home ${HOME_POS}"
            else
                echo "[WARN] Location '${LOCATION}' not found in locations.txt, using default"
            fi
        fi
    fi
    [ -n "${EXTRA_ARGS}" ] && CMD="${CMD} ${EXTRA_ARGS}"

    echo "  Mode:     Direct binary (headless, no MAVProxy)"
    echo "  Command:  ${CMD}"
    echo ""
    cd "${ARDUPILOT_DIR}"
    eval "${CMD}"
fi
