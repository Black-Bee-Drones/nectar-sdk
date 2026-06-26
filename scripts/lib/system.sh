#!/bin/bash

# True when every given package is installed (dpkg)
_all_dpkg_installed() {
    local p
    for p in "$@"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null \
            | grep -q "install ok installed" || return 1
    done
    return 0
}

cmd_system() {
    log_section "INSTALLING SYSTEM PACKAGES"

    # ROS 2 extras (MAVROS, cv_bridge, ...) only make sense once ROS 2 is set up.
    local ros_present=false
    if has_command ros2 \
        || [ -f /opt/ros/${ROS_DISTRO}/setup.bash ] \
        || ls /etc/apt/sources.list.d/ros2* &>/dev/null; then
        ros_present=true
    fi

    # Expected package set; skip apt entirely when it's already satisfied.
    local expected=("${SYSTEM_PACKAGES[@]}" "${GUI_SYSTEM_PACKAGES[@]}")
    [[ "$ros_present" == true ]] && expected+=("${ROS2_PACKAGES[@]}")

    if [[ "${FORCE:-}" != "1" ]] && _all_dpkg_installed "${expected[@]}"; then
        log_success "System packages already installed (FORCE=1 to re-run / 'make update' to upgrade)"
        SUDO usermod -a -G video "${USER:-root}" 2>/dev/null || true
        return 0
    fi

    SUDO apt-get update
    SUDO apt-get install -y --no-install-recommends \
        "${SYSTEM_PACKAGES[@]}" \
        "${GUI_SYSTEM_PACKAGES[@]}"

    if [[ "$ros_present" == true ]]; then
        log_info "Installing ROS2 extra packages (rviz2, cv_bridge, etc.)..."
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
