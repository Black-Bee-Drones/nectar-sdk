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

cmd_sim_install() {
    _sim_script install_sitl.sh "$@"
}

cmd_sim_install_gazebo() {
    _sim_script install_gazebo.sh "$@"
}

cmd_sim_start() {
    _sim_script start_sitl.sh "$@"
}

cmd_sim_start_outdoor() {
    _sim_script start_sitl.sh --gazebo "$@"
}

cmd_sim_start_indoor() {
    _sim_script start_sitl.sh --indoor "$@"
}

cmd_sim_mavros() {
    _source_ros_env
    ros2 launch nectar sitl.launch.py "$@"
}

cmd_sim_gazebo() {
    _source_ros_env
    ros2 launch nectar sitl_gazebo.launch.py "$@"
}

cmd_sim_outdoor() {
    _source_ros_env
    ros2 launch nectar sitl_gazebo.launch.py world:=outdoor "$@"
}

cmd_sim_outdoor_direct() {
    _source_ros_env
    ros2 launch nectar sitl_gazebo.launch.py world:=outdoor mavros:=false "$@"
}

cmd_sim_indoor() {
    _source_ros_env
    ros2 launch nectar sitl_gazebo.launch.py world:=indoor "$@"
}

cmd_sim_indoor_direct() {
    _source_ros_env
    ros2 launch nectar sitl_gazebo.launch.py world:=indoor mavros:=false "$@"
}

cmd_sim_stop() {
    log_info "Stopping simulation processes..."
    pkill -f arducopter 2>/dev/null || true
    pkill -f sim_vehicle.py 2>/dev/null || true
    pkill -f mavros_node 2>/dev/null || true
    pkill -f parameter_bridge 2>/dev/null || true
    pkill -f gz_vision_source 2>/dev/null || true
    pkill -f vision_pose_node 2>/dev/null || true
    pkill -f "gz sim" 2>/dev/null || true
    pkill -f "ruby.*gz" 2>/dev/null || true
    sleep 2
    # Force-kill any survivors
    pkill -9 -f arducopter 2>/dev/null || true
    pkill -9 -f "gz sim" 2>/dev/null || true
    pkill -9 -f mavros_node 2>/dev/null || true
    pkill -9 -f parameter_bridge 2>/dev/null || true
    pkill -9 -f gz_vision_source 2>/dev/null || true
    pkill -9 -f vision_pose_node 2>/dev/null || true
    log_success "Simulation stopped"
}
