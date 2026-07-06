#!/bin/bash

# Simulation commands — thin wrappers around scripts/simulation/*.
# Sources ROS2 environment for launch commands.

_sim_script() {
    local script="${PROJECT_DIR}/scripts/simulation/$1"
    shift
    if [ ! -f "$script" ]; then
        log_error "Script not found: $script"
        exit 1
    fi
    "$script" "$@"
}

_source_ros_env() {
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    if [ -f "${WORKSPACE_DIR}/install/setup.bash" ]; then
        source "${WORKSPACE_DIR}/install/setup.bash"
    fi
}

# ── Unified simulation CLI ──────────────────────────────────────────────────
# One pattern for both firmwares. The two-terminal split is unavoidable (the
# autopilot SITL and the ROS stack are separate processes), so it is made
# symmetric:
#   sim-start  = Terminal 1: the simulator (ArduPilot SITL; for PX4 also Gazebo)
#   sim-bridge = Terminal 2: the ROS stack (Gazebo+MAVROS for ArduPilot; MAVROS
#                for PX4). ENV must match between the two terminals.
#
# Axes (defaults): FIRMWARE=ardupilot  ENV=outdoor  PROTOCOL=mavros
# Any non-flag tokens are forwarded to the underlying script/launch (ARGS=...).

_sim_parse() {
    _SIM_FIRMWARE="ardupilot"
    _SIM_ENV="outdoor"
    _SIM_PROTOCOL="mavros"
    _SIM_EXTRA=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --firmware) _SIM_FIRMWARE="$2"; shift 2 ;;
            --env)      _SIM_ENV="$2"; shift 2 ;;
            --protocol) _SIM_PROTOCOL="$2"; shift 2 ;;
            *)          _SIM_EXTRA+=("$1"); shift ;;
        esac
    done
}

_sim_validate_firmware() {
    case "$_SIM_FIRMWARE" in
        ardupilot|px4) ;;
        *) log_error "Unknown FIRMWARE '$_SIM_FIRMWARE' (valid: ardupilot, px4)"; exit 1 ;;
    esac
}

_sim_validate_env() {
    case "$_SIM_ENV" in
        outdoor|indoor) ;;
        *) log_error "Unknown ENV '$_SIM_ENV' (valid: outdoor, indoor)"; exit 1 ;;
    esac
}

cmd_sim_install() {
    _sim_parse "$@"
    case "$_SIM_FIRMWARE" in
        ardupilot)
            _sim_script install_sitl.sh "${_SIM_EXTRA[@]}"
            _sim_script install_gazebo.sh
            ;;
        px4)
            _sim_script install_px4.sh "${_SIM_EXTRA[@]}"
            ;;
        all)
            _sim_script install_sitl.sh
            _sim_script install_gazebo.sh
            _sim_script install_px4.sh "${_SIM_EXTRA[@]}"
            ;;
        *)
            log_error "Unknown FIRMWARE '$_SIM_FIRMWARE' (valid: ardupilot, px4, all)"
            exit 1
            ;;
    esac
}

# Terminal 1 — the simulator (autopilot SITL; PX4 also starts Gazebo here).
cmd_sim_start() {
    _sim_parse "$@"
    _sim_validate_firmware
    _sim_validate_env
    case "$_SIM_FIRMWARE" in
        ardupilot)
            case "$_SIM_ENV" in
                outdoor) _sim_script start_sitl.sh --gazebo "${_SIM_EXTRA[@]}" ;;
                indoor)  _sim_script start_sitl.sh --indoor "${_SIM_EXTRA[@]}" ;;
            esac
            ;;
        px4)
            case "$_SIM_ENV" in
                outdoor)
                    # Shared Nectar outdoor world + x500_nectar (matched sensors),
                    # so both firmwares fly the same arena.
                    _sim_script start_px4.sh --model x500_nectar \
                        --world outdoor_field_px4 --autostart 4001 "${_SIM_EXTRA[@]}"
                    ;;
                indoor)
                    # PX4's built-in vision model flies GPS-denied via onboard VIO.
                    _sim_script start_px4.sh --model x500_vision "${_SIM_EXTRA[@]}"
                    ;;
            esac
            ;;
    esac
}

# Terminal 2 — the ROS stack that connects to the running simulator.
cmd_sim_bridge() {
    _sim_parse "$@"
    _sim_validate_firmware
    _sim_validate_env
    _source_ros_env
    case "$_SIM_FIRMWARE" in
        ardupilot)
            case "$_SIM_PROTOCOL" in
                mavros)
                    ros2 launch nectar sitl_gazebo.launch.py \
                        world:="$_SIM_ENV" "${_SIM_EXTRA[@]}"
                    ;;
                mavlink)
                    ros2 launch nectar sitl_gazebo.launch.py \
                        world:="$_SIM_ENV" mavros:=false "${_SIM_EXTRA[@]}"
                    ;;
                *)
                    log_error "Unknown PROTOCOL '$_SIM_PROTOCOL' (valid: mavros, mavlink)"
                    exit 1
                    ;;
            esac
            ;;
        px4)
            case "$_SIM_PROTOCOL" in
                mavros)
                    if [ "$_SIM_ENV" = "indoor" ]; then
                        ros2 launch nectar px4_sitl.launch.py vision:=true "${_SIM_EXTRA[@]}"
                    else
                        ros2 launch nectar px4_sitl.launch.py gz_bridge:=true "${_SIM_EXTRA[@]}"
                    fi
                    ;;
                mavlink)
                    # Direct-pymavlink (drone "px4_mavlink"): the drone connects
                    # to UDP 14540 itself, so skip MAVROS and bridge cameras only.
                    if [ "$_SIM_ENV" = "indoor" ]; then
                        ros2 launch nectar px4_sitl.launch.py mavros:=false "${_SIM_EXTRA[@]}"
                    else
                        ros2 launch nectar px4_sitl.launch.py mavros:=false gz_bridge:=true \
                            "${_SIM_EXTRA[@]}"
                    fi
                    ;;
                dds)
                    if ! command -v MicroXRCEAgent >/dev/null 2>&1; then
                        log_error "MicroXRCEAgent not found. Install the native uXRCE-DDS path:"
                        log_error "  make sim-install FIRMWARE=px4 ARGS=--native"
                        exit 1
                    fi
                    log_info "Starting Micro XRCE-DDS Agent on udp4 :8888..."

                    LD_LIBRARY_PATH="${HOME}/.local/lib:${LD_LIBRARY_PATH:-}" \
                        MicroXRCEAgent udp4 -p 8888 "${_SIM_EXTRA[@]}"
                    ;;
                *)
                    log_error "Unknown PROTOCOL '$_SIM_PROTOCOL' for px4 (valid: mavros, mavlink, dds)"
                    exit 1
                    ;;
            esac
            ;;
    esac
}

# Stop every simulation process for both firmwares.
cmd_sim_stop() {
    log_info "Stopping all simulation processes (ArduPilot + PX4)..."
    # Autopilot SITL
    pkill -f arducopter 2>/dev/null || true
    pkill -f sim_vehicle.py 2>/dev/null || true
    pkill -f "px4_sitl" 2>/dev/null || true
    pkill -f "bin/px4" 2>/dev/null || true
    pkill -f MicroXRCEAgent 2>/dev/null || true
    # Shared ROS stack + Gazebo
    pkill -f mavros_node 2>/dev/null || true
    pkill -f parameter_bridge 2>/dev/null || true
    pkill -f gz_vision_source 2>/dev/null || true
    pkill -f vision_pose_node 2>/dev/null || true
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "ruby.*gz" 2>/dev/null || true
    sleep 2
    # Force-kill any survivors
    pkill -9 -f arducopter 2>/dev/null || true
    pkill -9 -f "bin/px4" 2>/dev/null || true
    pkill -9 -f MicroXRCEAgent 2>/dev/null || true
    pkill -9 -f "gz sim" 2>/dev/null || true
    pkill -9 -f mavros_node 2>/dev/null || true
    pkill -9 -f parameter_bridge 2>/dev/null || true
    pkill -9 -f gz_vision_source 2>/dev/null || true
    pkill -9 -f vision_pose_node 2>/dev/null || true
    log_success "Simulation stopped"
}
