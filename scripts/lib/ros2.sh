#!/bin/bash

cmd_ros2_install() {
    log_section "INSTALLING ROS 2 ${ROS_DISTRO^^}"

    if has_command ros2; then
        log_info "ROS 2 already installed"
        if [[ "${NON_INTERACTIVE:-}" != "true" ]]; then
            read -p "Reinstall? (y/N): " -n 1 -r && echo
            [[ ! $REPLY =~ ^[Yy]$ ]] && return 0
        else
            return 0
        fi
    fi

    SUDO curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | \
        SUDO tee /etc/apt/sources.list.d/ros2.list > /dev/null

    SUDO apt-get update
    SUDO apt-get install -y "${ROS2_PACKAGES[@]}" python3-colcon-common-extensions python3-rosdep

    log_success "ROS 2 ${ROS_DISTRO^} installed"
}

cmd_geographiclib() {
    log_section "INSTALLING GEOGRAPHICLIB DATASETS"
    if [ -d /usr/share/GeographicLib/geoids ] || [ -d /usr/local/share/GeographicLib/geoids ]; then
        log_success "GeographicLib datasets already present (skipping)"
        return 0
    fi
    local tmp="/tmp/install_geographiclib_datasets.sh"
    wget -q https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh \
        -O "$tmp"
    chmod +x "$tmp"
    SUDO "$tmp"
    rm -f "$tmp"
    log_success "GeographicLib configured"
}

cmd_ros2_env() {
    log_section "CONFIGURING ROS 2 ENVIRONMENT"
    cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    sed -i '/# ROS 2 Configuration/,/# End ROS 2 Configuration/d' ~/.bashrc 2>/dev/null || true

    cat >> ~/.bashrc << EOF

# ROS 2 Configuration
source /opt/ros/${ROS_DISTRO}/setup.bash
[ -f "${WORKSPACE_DIR}/install/local_setup.bash" ] && source ${WORKSPACE_DIR}/install/local_setup.bash
source /usr/share/colcon_cd/function/colcon_cd.sh
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID}
# Nectar SDK Python venv (uv): opt-in, NOT auto-activated, so it stays out of the
# way of your other projects/workspaces. Run 'nectar-activate' to enter it and the
# built-in 'deactivate' to leave.
nectar-activate() {
    if [ -f "${NECTAR_VENV}/bin/activate" ]; then
        source "${NECTAR_VENV}/bin/activate"
    else
        echo "Nectar venv not found at ${NECTAR_VENV} — run 'make install-all' first."
    fi
}
# End ROS 2 Configuration
EOF
    log_success "Environment configured. Run: source ~/.bashrc"
    log_info "Python env is opt-in: run 'nectar-activate' to enter it (and 'deactivate' to leave)."
    log_info "Prefer it always on? Add to ~/.bashrc:  source ${NECTAR_VENV}/bin/activate"
}

cmd_rosdep_init() {
    log_section "INITIALIZING ROSDEP"
    if [ ! -f "/etc/ros/rosdep/sources.list.d/20-default.list" ]; then
        SUDO rosdep init 2>/dev/null || true
    fi
    rosdep update 2>/dev/null || (rosdep fix-permissions 2>/dev/null && rosdep update)
    log_success "rosdep initialized"
}
