#!/bin/bash
# =============================================================================
# start_px4.sh — Start PX4 SITL (+ Gazebo) for Nectar SDK
#
# Launches PX4 SITL with a Gazebo model (default gz_x500). PX4 starts Gazebo
# itself; the offboard MAVLink API is exposed on UDP 14540, which MAVROS
# connects to (see: ros2 launch nectar px4_sitl.launch.py).
#
# Usage:
#   ./scripts/simulation/start_px4.sh [options]
#
# Options:
#   --dir <path>     PX4-Autopilot directory (default: ~/PX4-Autopilot)
#   --model <name>   Gazebo vehicle model (default: x500). Other examples:
#                    x500_depth (front depth cam), x500_lidar_down (down lidar),
#                    x500_nectar (Nectar SDK matched sensor suite).
#   --world <name>   PX4 Gazebo world (default: PX4 default). e.g. walls, baylands,
#                    outdoor_field_px4, indoor_room_px4 (Nectar shared arenas).
#   --speedup <N>    Simulation speed factor (default: 1)
#   --home <lat,lon,alt>   Custom home/takeoff location
#   --headless       Run Gazebo without the GUI
#   --follow         Use PX4's follow camera (default: free orbit/zoom camera,
#                    matching the ArduPilot Gazebo view)
#   --autostart <N>  PX4 SYS_AUTOSTART id. Required for non-stock models that have
#                    no <id>_gz_<model> airframe file (e.g. x500_nectar). Triggers
#                    direct invocation of build/px4_sitl_default/bin/px4 with the
#                    requested model+world env (still uses standard rcS).
#                    Use 4001 for any x500 derivative.
#   --params <file>  Param env under nectar/simulation/params/ (or absolute path).
#                    NAME=VALUE → PX4_PARAM_NAME. Auto: indoor_room_px4 →
#                    px4_indoor.env, outdoor_field_px4 → px4_outdoor.env.
#   --pose <x,y,z[,r,p,y]>  Gazebo spawn pose (PX4_GZ_MODEL_POSE). Indoor
#                    default for indoor_room_px4 is -5,0,0.2
#   --extra <args>   Extra arguments appended to the make command
#
# Examples:
#   ./scripts/simulation/start_px4.sh
#   ./scripts/simulation/start_px4.sh --model x500_depth
#   ./scripts/simulation/start_px4.sh --world walls --headless
#   ./scripts/simulation/start_px4.sh --home -22.001,-47.001,850
#   ./scripts/simulation/start_px4.sh --model x500_nectar --world outdoor_field_px4 --autostart 4001
#   ./scripts/simulation/start_px4.sh --model x500_nectar --world indoor_room_px4 \
#       --autostart 4001 --params px4_indoor.env
# =============================================================================
set -euo pipefail

unset MAKEFLAGS MAKEOVERRIDES MFLAGS MAKELEVEL 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PARAMS_DIR="${PROJECT_DIR}/nectar/simulation/params"

PX4_DIR="${PX4_AUTOPILOT_DIR:-${HOME}/PX4-Autopilot}"
MODEL="x500"
WORLD=""
SPEEDUP="1"
HEADLESS_VAL="0"
FOLLOW_VAL="0"
HOME_POS=""
EXTRA_ARGS=""
AUTOSTART=""
PARAMS_FILE=""
MODEL_POSE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)       PX4_DIR="$2"; shift 2 ;;
        --model)     MODEL="$2"; shift 2 ;;
        --world)     WORLD="$2"; shift 2 ;;
        --speedup)   SPEEDUP="$2"; shift 2 ;;
        --home)      HOME_POS="$2"; shift 2 ;;
        --headless)  HEADLESS_VAL="1"; shift ;;
        --follow)    FOLLOW_VAL="1"; shift ;;
        --autostart) AUTOSTART="$2"; shift 2 ;;
        --params)    PARAMS_FILE="$2"; shift 2 ;;
        --pose)      MODEL_POSE="$2"; shift 2 ;;
        --extra)     EXTRA_ARGS="$2"; shift 2 ;;
        -h|--help)
            head -n 40 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Validate ────────────────────────────────────────────────────────────────
if [ ! -d "${PX4_DIR}" ]; then
    echo "[ERROR] PX4-Autopilot not found at ${PX4_DIR}"
    echo "        Run: ./scripts/simulation/install_px4.sh"
    exit 1
fi

# Append world to the model target (PX4 syntax: gz_<model>_<world>) or set via env.
TARGET="gz_${MODEL}"
if [ -n "${WORLD}" ]; then
    export PX4_GZ_WORLD="${WORLD}"
fi

[ -n "${HOME_POS}" ] && export PX4_HOME_LAT="${HOME_POS%%,*}" && \
    PX4_REST="${HOME_POS#*,}" && export PX4_HOME_LON="${PX4_REST%%,*}" && \
    export PX4_HOME_ALT="${PX4_REST#*,}"

export PX4_SIM_SPEED_FACTOR="${SPEEDUP}"

# Offboard-from-a-companion (SIM ONLY). Without these, headless OFFBOARD arms then
# failsafes on missing RC/GCS ("No manual control stick input") or refuses arm.
# Documented triad: NAV_DLL_ACT=0, NAV_RCL_ACT=0, COM_RCL_EXCEPT=4 (Offboard bit)
# https://discuss.px4.io/t/offboard-mode-in-sitl/25727
# https://github.com/PX4/PX4-Autopilot/issues/19349
# Real hardware keeps stock failsafes; PX4_PARAM_* only overrides SITL.
export PX4_PARAM_NAV_DLL_ACT=0
export PX4_PARAM_NAV_RCL_ACT=0
export PX4_PARAM_COM_RCL_EXCEPT=4

# Indoor shared room: spawn in the open area (same x=-5 as ArduPilot iris).
if [ -z "${MODEL_POSE}" ] && [ "${WORLD}" = "indoor_room_px4" ]; then
    MODEL_POSE="-5,0,0.2"
fi
if [ -n "${MODEL_POSE}" ]; then
    export PX4_GZ_MODEL_POSE="${MODEL_POSE}"
fi

# Apply optional param env file (NAME=VALUE → PX4_PARAM_NAME=VALUE).
_apply_params_file() {
    local file="$1"
    local path="$file"
    if [ ! -f "${path}" ] && [ -f "${PARAMS_DIR}/${file}" ]; then
        path="${PARAMS_DIR}/${file}"
    fi
    if [ ! -f "${path}" ]; then
        echo "[ERROR] Params file not found: ${file}"
        echo "        Looked at ${file} and ${PARAMS_DIR}/${file}"
        exit 1
    fi
    echo "  Params:   ${path}"
    local line name value
    while IFS= read -r line || [ -n "${line}" ]; do
        # Strip comments and blank lines
        line="${line%%#*}"
        line="$(echo "${line}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -z "${line}" ] && continue
        name="${line%%=*}"
        value="${line#*=}"
        name="$(echo "${name}" | sed 's/[[:space:]]*$//')"
        value="$(echo "${value}" | sed 's/^[[:space:]]*//')"
        [ -z "${name}" ] && continue
        export "PX4_PARAM_${name}=${value}"
    done < "${path}"
}

# Auto-select env params so indoor EV and outdoor GNSS cannot pollute each other
# via parameters.bson (PX4 stores non-default EKF2_* across SITL restarts).
if [ -z "${PARAMS_FILE}" ]; then
    case "${WORLD}" in
        indoor_room_px4)   PARAMS_FILE="px4_indoor.env" ;;
        outdoor_field_px4) PARAMS_FILE="px4_outdoor.env" ;;
    esac
fi
if [ -n "${PARAMS_FILE}" ]; then
    _apply_params_file "${PARAMS_FILE}"
fi

# PX4 treats ANY non-empty HEADLESS value (even "0") as headless: it gates the
# GUI with `[ -z "$HEADLESS" ]`. So only export it when headless is requested,
# and unset it otherwise so the Gazebo GUI window opens.
if [ "${HEADLESS_VAL}" = "1" ]; then
    export HEADLESS=1
else
    unset HEADLESS
fi

# Camera: by default disable PX4's follow camera so the GUI uses a free
# orbit/zoom camera like the ArduPilot Gazebo view. With the follow camera the
# view tracks the drone, so lateral motion (e.g. a position box) looks like the
# world sliding and only yaw appears as movement. Pass --follow to keep it.
if [ "${FOLLOW_VAL}" = "1" ]; then
    unset PX4_GZ_NO_FOLLOW
else
    export PX4_GZ_NO_FOLLOW=1
fi

# ── Launch ──────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║  Nectar SDK — PX4 SITL                          ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Model:    ${MODEL}"
echo "  World:    ${WORLD:-default}"
echo "  Pose:     ${MODEL_POSE:-PX4 default}"
echo "  Speedup:  ${SPEEDUP}x"
echo "  Headless: $([ "${HEADLESS_VAL}" = "1" ] && echo "yes (no GUI)" || echo "no (GUI window)")"
echo "  Camera:   $([ "${FOLLOW_VAL}" = "1" ] && echo "follow drone" || echo "free (orbit/zoom)")"
echo "  Offboard: udp://:14540  (MAVROS connects here)"
echo ""
echo "  Connect MAVROS in another terminal with:"
echo "    ros2 launch nectar px4_sitl.launch.py"
echo ""

cd "${PX4_DIR}"

if [ -n "${AUTOSTART}" ]; then
    # Direct binary invocation. Used for custom models that don't ship with a
    # <id>_gz_<model> airframe file (e.g. x500_nectar). The PX4 binary still
    # runs the standard rcS; PX4_SYS_AUTOSTART takes precedence over the
    # model-name lookup, so we reuse the parent airframe (e.g. 4001 for any
    # x500 derivative). Replicates the env that PX4's gz_<model> make-targets
    # set (PX4_SIM_MODEL=gz_<model>, PX4_GZ_WORLD, GZ_IP=127.0.0.1).
    PX4_BIN="${PX4_DIR}/build/px4_sitl_default/bin/px4"
    PX4_ROOTFS="${PX4_DIR}/build/px4_sitl_default/rootfs"
    if [ ! -x "${PX4_BIN}" ]; then
        echo "[ERROR] ${PX4_BIN} not found. Run install_px4.sh first."; exit 1
    fi
    export PX4_SIM_MODEL="gz_${MODEL}"
    export PX4_SYS_AUTOSTART="${AUTOSTART}"
    export GZ_IP="127.0.0.1"
    echo "  Autostart: ${AUTOSTART} (direct binary invocation)"
    echo "  Command:   PX4_SIM_MODEL=${PX4_SIM_MODEL} PX4_SYS_AUTOSTART=${AUTOSTART} ${PX4_BIN}"
    echo ""
    cd "${PX4_ROOTFS}"
    exec "${PX4_BIN}"
else
    CMD="make px4_sitl ${TARGET}"
    [ -n "${EXTRA_ARGS}" ] && CMD="${CMD} ${EXTRA_ARGS}"
    echo "  Command:  ${CMD}"
    echo ""
    eval "${CMD}"
fi
