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
#                    x500_nectar (Nectar SDK matched sensor suite — outdoor world).
#   --world <name>   PX4 Gazebo world (default: PX4 default). e.g. walls, baylands,
#                    outdoor_field_px4 (Nectar shared outdoor scenery).
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
#   --extra <args>   Extra arguments appended to the make command
#
# Examples:
#   ./scripts/simulation/start_px4.sh
#   ./scripts/simulation/start_px4.sh --model x500_depth
#   ./scripts/simulation/start_px4.sh --world walls --headless
#   ./scripts/simulation/start_px4.sh --home -22.001,-47.001,850
#   ./scripts/simulation/start_px4.sh --model x500_nectar --world outdoor_field_px4 --autostart 4001
# =============================================================================
set -euo pipefail

unset MAKEFLAGS MAKEOVERRIDES MFLAGS MAKELEVEL 2>/dev/null || true

PX4_DIR="${PX4_AUTOPILOT_DIR:-${HOME}/PX4-Autopilot}"
MODEL="x500"
WORLD=""
SPEEDUP="1"
HEADLESS_VAL="0"
FOLLOW_VAL="0"
HOME_POS=""
EXTRA_ARGS=""
AUTOSTART=""

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
        --extra)     EXTRA_ARGS="$2"; shift 2 ;;
        -h|--help)
            head -n 30 "$0" | tail -n +2 | sed 's/^# //' | sed 's/^#//'
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

# Offboard-from-a-companion convenience (SIM ONLY): PX4 blocks arming with
# "Preflight Fail: No connection to the GCS" when NAV_DLL_ACT>0 and no GCS/RC
# heartbeat is seen (MAVROS announces itself as a companion, not a GCS). Disable
# the data-link / RC loss actions so MAVROS offboard can arm and fly headlessly.
# Real hardware (the `px4` drone) keeps its own failsafes; these only override
# the SITL parameters via PX4's PX4_PARAM_* mechanism.
export PX4_PARAM_NAV_DLL_ACT=0
export PX4_PARAM_NAV_RCL_ACT=0

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
