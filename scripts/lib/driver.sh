#!/bin/bash
# Real-hardware driver / bridge launcher — the real-world counterpart to the
# sim-start/sim-bridge commands. The SDK examples run with start_driver=False,
# so the driver or bridge the mission connects to must run in its own terminal;
# this starts the right one per platform. All commands below are exactly those
# documented in the module READMEs and launch files.
#
#   ./setup.sh driver <type> [--env outdoor|indoor] [passthrough...]
#   types: mavros | px4 | px4-dds | mavlink | px4_mavlink | bebop | crazyflie
#
# Connection overrides (env vars; sensible defaults per type):
#   FCU_URL   MAVROS fcu_url / vision-pose fcu_url   (e.g. serial:///dev/ttyUSB0:921600)
#   DEV BAUD  px4-dds serial agent device / baud     (default /dev/ttyUSB0 921600)
#   PORT      px4-dds UDP agent port                 (use UDP instead of serial)
#   IP        Bebop drone IP                         (default 192.168.42.1)

_driver_source_ros() {
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    [ -f "${WORKSPACE_DIR}/install/setup.bash" ] && source "${WORKSPACE_DIR}/install/setup.bash"
}

_driver_parse() {
    _DRV_ENV="outdoor"
    _DRV_EXTRA=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --env) _DRV_ENV="$2"; shift 2 ;;
            *)     _DRV_EXTRA+=("$1"); shift ;;
        esac
    done
    case "$_DRV_ENV" in
        outdoor|indoor) ;;
        *) log_error "Unknown ENV '$_DRV_ENV' (valid: outdoor, indoor)"; return 1 ;;
    esac
}

# ArduPilot/PX4 over MAVROS. Outdoor = the autopilot's MAVROS launch; indoor =
# the SDK vision-pose bridge (MAVROS backend), which also feeds VSLAM -> EKF.
_driver_mavros() {
    local launch="$1"   # apm.launch | px4.launch
    if [ "$_DRV_ENV" = "indoor" ]; then
        log_info "Indoor: vision-pose bridge (MAVROS backend) + MAVROS"
        ros2 launch nectar vision_pose.launch.py backend:=mavros \
            ${FCU_URL:+fcu_url:="$FCU_URL"} "${_DRV_EXTRA[@]}"
    else
        local url="${FCU_URL:-serial:///dev/ttyUSB0:921600}"
        log_info "MAVROS (${launch}) fcu_url:=${url}"
        ros2 launch mavros "$launch" fcu_url:="$url" "${_DRV_EXTRA[@]}"
    fi
}

# PX4 native uXRCE-DDS: the Micro XRCE-DDS Agent bridges the FCU to ROS 2.
# Serial by default (real FCU); set PORT to use UDP instead.
_driver_px4_dds() {
    if ! command -v MicroXRCEAgent >/dev/null 2>&1; then
        log_error "MicroXRCEAgent not found. Install it with: make drone-px4-dds"
        return 1
    fi
    if [ "$_DRV_ENV" = "indoor" ]; then
        log_info "Indoor px4_dds also needs a vision feed (separate terminal):"
        log_info "  ros2 launch nectar vision_pose.launch.py backend:=dds"
    fi
    if [ -n "${PORT:-}" ]; then
        log_info "Micro XRCE-DDS Agent on udp4 :${PORT}"
        LD_LIBRARY_PATH="${HOME}/.local/lib:${LD_LIBRARY_PATH:-}" \
            MicroXRCEAgent udp4 -p "$PORT" "${_DRV_EXTRA[@]}"
    else
        local dev="${DEV:-/dev/ttyUSB0}" baud="${BAUD:-921600}"
        log_info "Micro XRCE-DDS Agent on serial ${dev} @ ${baud}"
        LD_LIBRARY_PATH="${HOME}/.local/lib:${LD_LIBRARY_PATH:-}" \
            MicroXRCEAgent serial --dev "$dev" -b "$baud" "${_DRV_EXTRA[@]}"
    fi
}

# Direct pymavlink (drone "mavlink" / "px4_mavlink"): the mission opens the link
# itself, so outdoor needs no bridge. Indoor still needs the vision-pose feed.
_driver_mavlink() {
    if [ "$_DRV_ENV" = "indoor" ]; then
        log_info "Indoor: vision-pose bridge (MAVLink backend)"
        ros2 launch nectar vision_pose.launch.py backend:=mavlink \
            ${FCU_URL:+mavlink_url:="$FCU_URL"} "${_DRV_EXTRA[@]}"
    else
        log_info "Direct MAVLink: no bridge needed — the mission connects itself."
        log_info "Run it directly, e.g.:"
        log_info "  python3 nectar/nectar/examples/control/basic.py --drone mavlink --connection serial:///dev/ttyUSB0:921600"
    fi
}

_driver_bebop() {
    local ip="${IP:-192.168.42.1}"
    log_info "Bebop driver (ip:=${ip})"
    ros2 launch ros2_bebop_driver bebop_node_launch.xml ip:="$ip" "${_DRV_EXTRA[@]}"
}

_driver_crazyflie() {
    log_info "Crazyflie server (Crazyswarm2; uses your crazyflies.yaml)"
    ros2 launch crazyflie launch.py "${_DRV_EXTRA[@]}"
}

# Dispatcher: ./setup.sh driver <type> [--env ..] [passthrough]
cmd_driver() {
    local kind="${1:-}"
    shift 2>/dev/null || true
    case "$kind" in
        ""|list|-h|--help)
            echo "Usage: ./setup.sh driver <type> [--env outdoor|indoor] [extra]"
            echo "  types: mavros, px4, px4-dds, mavlink, px4_mavlink, bebop, crazyflie"
            echo "  env vars: FCU_URL, DEV, BAUD, PORT, IP"
            return 0
            ;;
    esac
    _driver_parse "$@" || return 1
    _driver_source_ros
    log_section "STARTING DRIVER: ${kind} (${_DRV_ENV})"
    case "$kind" in
        mavros)               _driver_mavros apm.launch ;;
        px4)                  _driver_mavros px4.launch ;;
        px4-dds|px4_dds)      _driver_px4_dds ;;
        mavlink|px4_mavlink)  _driver_mavlink ;;
        bebop)                _driver_bebop ;;
        crazyflie)            _driver_crazyflie ;;
        *)
            log_error "Unknown driver '$kind' (expected mavros|px4|px4-dds|mavlink|bebop|crazyflie)"
            return 1
            ;;
    esac
}

# Stop every real-hardware driver/bridge process (graceful, then force).
cmd_driver_stop() {
    log_info "Stopping real-hardware drivers/bridges..."
    local pats=(mavros_node MicroXRCEAgent vision_pose_node bebop_driver "crazyflie.*launch" crazyflie_server)
    local p
    for p in "${pats[@]}"; do pkill -f "$p" 2>/dev/null || true; done
    sleep 2
    for p in "${pats[@]}"; do pkill -9 -f "$p" 2>/dev/null || true; done
    log_success "Drivers stopped"
}
