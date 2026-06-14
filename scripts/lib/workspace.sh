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
    if [ -f "install/setup.bash" ]; then
        source "install/setup.bash"
    fi
    log_success "Workspace built"
}

cmd_build_pkg() {
    log_section "BUILDING SDK PACKAGES"
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    colcon build --symlink-install --packages-select "$INTERFACES_PKG_NAME" "$ROS2_PKG_NAME"
    if [ -f "install/setup.bash" ]; then
        source "install/setup.bash"
    fi
    log_success "Packages built"
}

cmd_clean() {
    log_section "CLEANING SDK PACKAGES"
    cd "$WORKSPACE_DIR"
    rm -rf "build/${ROS2_PKG_NAME}" "build/${INTERFACES_PKG_NAME}" \
           "install/${ROS2_PKG_NAME}" "install/${INTERFACES_PKG_NAME}" \
           log/
    log_success "SDK packages cleaned (${ROS2_PKG_NAME}, ${INTERFACES_PKG_NAME})"
}

cmd_verify() {
    log_section "VERIFYING INSTALLATION"

    local _pass=0 _fail=0 _warn=0

    _check() {
        local desc="$1"; shift
        if eval "$@" >/dev/null 2>&1; then
            log_success "$desc"
            _pass=$((_pass + 1))
        else
            log_error "$desc"
            _fail=$((_fail + 1))
        fi
    }

    _check_opt() {
        local desc="$1"; shift
        if eval "$@" >/dev/null 2>&1; then
            log_success "$desc"
            _pass=$((_pass + 1))
        else
            log_warning "$desc (optional)"
            _warn=$((_warn + 1))
        fi
    }

    _ver() { python3 -c "import $1; print(getattr($1,'__version__',getattr($1,'VERSION','?')))" 2>/dev/null || echo "n/a"; }

    # --- Environment ---
    source "/opt/ros/${ROS_DISTRO}/setup.bash" 2>/dev/null || true
    [ -f "${WORKSPACE_DIR}/install/local_setup.bash" ] && \
        source "${WORKSPACE_DIR}/install/local_setup.bash" 2>/dev/null || true

    echo ""
    log_info "OS:     $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '\"')"
    log_info "Python: $(python3 --version 2>&1)"
    log_info "ROS:    ${ROS_DISTRO}"
    echo ""

    # --- ROS2 core ---
    _check  "ros2 CLI"                          'has_command ros2'
    _check  "colcon CLI"                         'has_command colcon'

    # --- ROS2 packages ---
    _check  "pkg: ${ROS2_PKG_NAME}"              'ros2 pkg list 2>/dev/null | grep -q "^${ROS2_PKG_NAME}$"'
    _check  "pkg: ${INTERFACES_PKG_NAME}"         'ros2 pkg list 2>/dev/null | grep -q "^${INTERFACES_PKG_NAME}$"'
    _check  "pkg: cv_bridge"                      'ros2 pkg list 2>/dev/null | grep -q cv_bridge'
    _check  "pkg: mavros"                         'ros2 pkg list 2>/dev/null | grep -q mavros'

    # --- Optional drone drivers ---
    _check_opt  "pkg: crazyflie_interfaces"       'ros2 pkg list 2>/dev/null | grep -q crazyflie_interfaces'
    _check_opt  "pkg: bebop_driver"               'ros2 pkg list 2>/dev/null | grep -q bebop_driver'

    # --- Core Python imports ---
    _check  "import numpy       ($(_ver numpy))"       'python3 -c "import numpy"'
    _check  "import cv2         ($(_ver cv2))"          'python3 -c "import cv2"'
    _check  "import scipy       ($(_ver scipy))"        'python3 -c "import scipy.special"'
    _check  "import PIL         ($(_ver PIL))"           'python3 -c "import PIL"'
    _check  "import yaml"                                'python3 -c "import yaml"'
    _check  "import cv_bridge"                           'python3 -c "from cv_bridge import CvBridge"'

    # --- numpy ABI compat ---
    _check  "numpy < 2.0 (cv_bridge compat)"  \
            'python3 -c "import numpy; assert int(numpy.__version__.split(\".\")[0]) < 2"'
    _check  "cv_bridge + numpy interop"  \
            'python3 -c "from cv_bridge import CvBridge; import numpy as np; CvBridge().cv2_to_imgmsg(np.zeros((10,10,3),dtype=np.uint8))"'

    # --- SDK modules ---
    _check      "import nectar"              'python3 -c "import nectar"'
    _check      "import nectar.vision"       'python3 -c "import nectar.vision"'
    _check      "import nectar.control"      'python3 -c "import nectar.control"'
    _check_opt  "import nectar.ai"           'python3 -c "import nectar.ai"'
    _check_opt  "import nectar.interface"    'python3 -c "import nectar.interface"'

    # --- Optional: Control deps ---
    _check_opt  "import shapely"      'python3 -c "import shapely"'
    _check_opt  "import sklearn"      'python3 -c "import sklearn"'
    _check_opt  "import mediapipe"    'python3 -c "import mediapipe"'

    # --- Optional: PyTorch ---
    if python3 -c "import torch" 2>/dev/null; then
        local tv; tv=$(python3 -c "import torch; print(torch.__version__)" 2>/dev/null)
        _check  "import torch       (${tv})"          'python3 -c "import torch"'
        _check  "import torchvision ($(_ver torchvision))" 'python3 -c "import torchvision"'

        if echo "$tv" | grep -q "+cu"; then
            _check "torch CUDA build (${tv})" 'true'
            _check "torch.cuda.is_available()" \
                   'python3 -c "import torch; assert torch.cuda.is_available(), \"no CUDA\""'
            _check "GPU tensor" \
                   'python3 -c "import torch; t=torch.randn(2,2).cuda(); assert t.is_cuda"'
            python3 -c "import torch; print('  GPU: ' + torch.cuda.get_device_name(0))" 2>/dev/null || true
        else
            log_info "torch ${tv} (CPU build — GPU checks skipped)"
        fi
    else
        log_warning "PyTorch: not installed (optional)"
        _warn=$((_warn + 1))
    fi

    # --- Optional: AI packages ---
    if python3 -c "import torch" 2>/dev/null; then
        _check_opt  "import ultralytics    ($(_ver ultralytics))"    'python3 -c "import ultralytics"'
        _check_opt  "import transformers   ($(_ver transformers))"   'python3 -c "import transformers"'
        _check_opt  "import supervision    ($(_ver supervision))"    'python3 -c "import supervision"'
        _check_opt  "import albumentations ($(_ver albumentations))" 'python3 -c "import albumentations"'
        _check_opt  "import timm           ($(_ver timm))"           'python3 -c "import timm"'
        _check_opt  "import rfdetr"                                   'python3 -c "import rfdetr"'
        _check_opt  "import datasets"                                 'python3 -c "import datasets"'
        _check_opt  "import huggingface_hub"                          'python3 -c "import huggingface_hub"'
        _check_opt  "import roboflow"                                 'python3 -c "import roboflow"'
        _check_opt  "import accelerate"                               'python3 -c "import accelerate"'
        _check_opt  "import tensorboard"                              'python3 -c "import tensorboard"'
    fi

    # --- Summary ---
    echo ""
    log_section "RESULT: ${_pass} passed, ${_fail} failed, ${_warn} warnings"
    if [[ $_fail -gt 0 ]]; then
        log_error "Some checks failed!"
        return 1
    else
        log_success "All checks passed."
    fi
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
