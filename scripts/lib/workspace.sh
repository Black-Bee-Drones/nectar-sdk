#!/bin/bash

cmd_clone_project() {
    log_section "CLONING PROJECT"
    mkdir -p "${WORKSPACE_DIR}/src"
    cd "${WORKSPACE_DIR}/src"

    if [ ! -d "$PROJECT_DIR_NAME" ]; then
        git clone "$PROJECT_REPO"
    else
        log_info "Updating existing repository..."
        cd "$PROJECT_DIR_NAME" && git pull origin main && cd ..
    fi
    log_success "Project ready in ${WORKSPACE_DIR}/src/${PROJECT_DIR_NAME}"
}

cmd_ros2_deps() {
    log_section "INSTALLING ROS2 PACKAGE DEPENDENCIES"
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    rosdep install -i --from-path src --rosdistro "$ROS_DISTRO" -r -y
    log_success "ROS2 dependencies installed"
}

cmd_build() {
    log_section "BUILDING WORKSPACE"
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    colcon build --symlink-install
    log_success "Workspace built"
}

cmd_build_pkg() {
    log_section "BUILDING SDK PACKAGES"
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    colcon build --symlink-install --packages-select "$INTERFACES_PKG_NAME" "$ROS2_PKG_NAME"
    log_success "Packages built"
}

cmd_clean() {
    log_section "CLEANING WORKSPACE"
    cd "$WORKSPACE_DIR"
    rm -rf build/ install/ log/
    log_success "Workspace cleaned"
}

cmd_verify() {
    log_section "VERIFYING INSTALLATION"
    source "/opt/ros/${ROS_DISTRO}/setup.bash" 2>/dev/null || true
    [ -f "${WORKSPACE_DIR}/install/local_setup.bash" ] && source "${WORKSPACE_DIR}/install/local_setup.bash"

    has_command ros2 && log_success "ROS 2: ${ROS_DISTRO}" || log_error "ROS 2 not found"

    python3 -c "import numpy; print('numpy:', numpy.__version__)" 2>/dev/null \
        || log_warning "numpy: not found"
    python3 -c "import cv2; print('opencv:', cv2.__version__)" 2>/dev/null \
        || log_warning "opencv: not found"
    python3 -c "import scipy; print('scipy:', scipy.__version__)" 2>/dev/null \
        || log_warning "scipy: not found"
    python3 -c "import PySide6; print('PySide6:', PySide6.__version__)" 2>/dev/null \
        || log_warning "PySide6: not installed (optional)"
    python3 -c "import ultralytics; print('ultralytics:', ultralytics.__version__)" 2>/dev/null \
        || log_warning "ultralytics: not installed (optional)"
    python3 -c "import torch; print('PyTorch:', torch.__version__, '(CUDA:', torch.cuda.is_available(), ')')" 2>/dev/null \
        || log_warning "PyTorch: not installed (optional)"

    ros2 pkg list 2>/dev/null | grep -q "$ROS2_PKG_NAME" \
        && log_success "${ROS2_PKG_NAME}: OK" \
        || log_warning "${ROS2_PKG_NAME}: not found in ROS2"

    log_success "Verification complete"
}

cmd_test() {
    log_section "RUNNING TESTS"
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    source install/local_setup.bash
    colcon test --packages-select "$ROS2_PKG_NAME"
    colcon test-result --verbose
    log_success "Tests complete"
}
