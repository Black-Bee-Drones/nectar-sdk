#!/bin/bash

cmd_system() {
    log_section "INSTALLING SYSTEM PACKAGES"
    SUDO apt-get update
    SUDO apt-get install -y --no-install-recommends \
        "${SYSTEM_PACKAGES[@]}" \
        "${GUI_SYSTEM_PACKAGES[@]}"

    # Install ROS2 extra packages if ROS2 is available
    if has_command ros2 \
        || [ -f /opt/ros/${ROS_DISTRO}/setup.bash ] \
        || ls /etc/apt/sources.list.d/ros2* &>/dev/null; then
        log_info "Installing ROS2 extra packages (MAVROS, cv_bridge, etc.)..."
        SUDO apt-get install -y --no-install-recommends "${ROS2_PACKAGES[@]}"
    fi

    SUDO usermod -a -G video "${USER:-root}"
    log_success "System packages installed"
}

cmd_update_system() {
    log_section "UPDATING SYSTEM"
    SUDO apt-get update && SUDO apt-get upgrade -y
    log_success "System updated"
}
