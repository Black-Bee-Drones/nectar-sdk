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

# Verify the installation. Checks are organized into groups; pass an optional
# group key to run only that group (e.g. `verify ai`). Valid keys:
#   ros python sdk control vision sensors interface realsense ai nodes  (default: all)
#
# Speed: presence/version come from importlib.util.find_spec / importlib.metadata,
# which do NOT import the module, so heavyweight optional deps (torch, transformers,
# ...) cost milliseconds. Real imports are used only where they add signal
# (core deps, first-party nectar.* modules, cv_bridge interop, torch CUDA).
cmd_verify() {
    local filter="${1:-all}"
    case "$filter" in
        all|ros|python|sdk|control|vision|sensors|interface|realsense|ai|nodes) ;;
        *)  log_error "Unknown verify group: ${filter}"
            log_info  "Valid groups: ros python sdk control vision sensors interface realsense ai nodes (default: all)"
            return 1 ;;
    esac
    log_section "VERIFYING INSTALLATION"

    local _pass=0 _fail=0 _warn=0      # totals
    local _gp=0 _gf=0 _gw=0            # current-group counters
    local _active=0 _gname=""

    _spec() { python3 -c "import importlib.util as u,sys; sys.exit(0 if u.find_spec('$1') else 1)" 2>/dev/null; }
    _ver()  { python3 -c "import importlib.metadata as m; print(m.version('$1'))" 2>/dev/null || echo "?"; }

    _gsummary() {
        [[ -n "$_gname" && "$_active" == "1" && $((_gp + _gf + _gw)) -gt 0 ]] && \
            echo -e "   ${BLUE}- ${_gp} ok, ${_gf} fail, ${_gw} warn${NC}"
        return 0
    }

    # _group <title> <key>: close the previous group, open a new one. The group
    # is active (its checks run + print) only when the filter selects it.
    _group() {
        _gsummary
        _gname="$1"; _gp=0; _gf=0; _gw=0
        if [[ "$filter" == "all" || "$filter" == "$2" ]]; then
            _active=1
            echo ""
            echo -e "${PURPLE}-- $1 --${NC}"
        else
            _active=0
        fi
    }

    _req() {  # _req <label> <command>
        [[ "$_active" == "1" ]] || return 0
        if eval "$2" >/dev/null 2>&1; then
            log_success "$1"; _pass=$((_pass + 1)); _gp=$((_gp + 1))
        else
            log_error "$1"; _fail=$((_fail + 1)); _gf=$((_gf + 1))
        fi
    }

    _opt() {  # _opt <label> <command>
        [[ "$_active" == "1" ]] || return 0
        if eval "$2" >/dev/null 2>&1; then
            log_success "$1"; _pass=$((_pass + 1)); _gp=$((_gp + 1))
        else
            log_warning "$1 (optional)"; _warn=$((_warn + 1)); _gw=$((_gw + 1))
        fi
    }

    # --- Environment (always shown) ---
    source "/opt/ros/${ROS_DISTRO}/setup.bash" 2>/dev/null || true
    local _ws_sourced="no"
    if [ -f "${WORKSPACE_DIR}/install/local_setup.bash" ]; then
        source "${WORKSPACE_DIR}/install/local_setup.bash" 2>/dev/null && _ws_sourced="yes"
    fi
    echo ""
    log_info "OS:        $(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '\"')"
    log_info "Python:    $(python3 --version 2>&1)"
    log_info "ROS:       ${ROS_DISTRO}"
    log_info "Workspace: ${WORKSPACE_DIR} (overlay sourced: ${_ws_sourced})"
    [[ "$filter" != "all" ]] && log_info "Filter:    ${filter}"

    # Cache expensive ROS queries once (reused across groups).
    local _pkgs _execs
    _pkgs="$(ros2 pkg list 2>/dev/null)"
    _execs="$(ros2 pkg executables ${ROS2_PKG_NAME} 2>/dev/null)"

    # --- ROS 2 core ---
    _group "ROS 2 core" ros
    _req "ros2 CLI"   'has_command ros2'
    _req "colcon CLI" 'has_command colcon'

    # --- ROS 2 packages ---
    _group "ROS 2 packages" ros
    _req "pkg: ${ROS2_PKG_NAME}"         'grep -qx "${ROS2_PKG_NAME}" <<<"$_pkgs"'
    _req "pkg: ${INTERFACES_PKG_NAME}"   'grep -qx "${INTERFACES_PKG_NAME}" <<<"$_pkgs"'
    _req "pkg: cv_bridge"                'grep -q "cv_bridge" <<<"$_pkgs"'
    _req "pkg: tf_transformations"       'grep -q "tf_transformations" <<<"$_pkgs"'
    _req "pkg: image_geometry"           'grep -q "image_geometry" <<<"$_pkgs"'
    _opt "pkg: mavros"                   'grep -q "mavros" <<<"$_pkgs"'
    _opt "pkg: crazyflie_interfaces"     'grep -q "crazyflie_interfaces" <<<"$_pkgs"'
    _opt "pkg: bebop_driver"             'grep -q "bebop_driver" <<<"$_pkgs"'
    _opt "pkg: realsense2_camera"        'grep -q "realsense2_camera" <<<"$_pkgs"'

    # --- Core Python ---
    _group "Core Python" python
    _req "numpy ($(_ver numpy))"           'python3 -c "import numpy"'
    _req "numpy < 2.0 (cv_bridge ABI)"     'python3 -c "import numpy,sys; sys.exit(0 if int(numpy.__version__.split(chr(46))[0])<2 else 1)"'
    _req "opencv ($(_ver opencv-python))"  'python3 -c "import cv2"'
    _req "scipy ($(_ver scipy))"           'python3 -c "import scipy.special"'
    _req "pillow ($(_ver pillow))"         'python3 -c "import PIL"'
    _req "pyyaml ($(_ver pyyaml))"         'python3 -c "import yaml"'
    _req "tqdm ($(_ver tqdm))"             'python3 -c "import tqdm"'
    _req "catkin_pkg ($(_ver catkin-pkg))" 'python3 -c "import catkin_pkg"'
    _req "cv_bridge import"                'python3 -c "from cv_bridge import CvBridge"'
    _req "cv_bridge + numpy interop"       'python3 -c "from cv_bridge import CvBridge; import numpy as np; CvBridge().cv2_to_imgmsg(np.zeros((10,10,3),dtype=np.uint8))"'

    # --- SDK modules (first-party; real import to catch breakage) ---
    _group "SDK modules" sdk
    _req "import nectar"           'python3 -c "import nectar"'
    _req "import nectar.vision"    'python3 -c "import nectar.vision"'
    _req "import nectar.control"   'python3 -c "import nectar.control"'
    _req "import nectar.sensors"   'python3 -c "import nectar.sensors"'
    _opt "import nectar.ai"        'python3 -c "import nectar.ai"'
    _opt "import nectar.interface" 'python3 -c "import nectar.interface"'

    # --- Control deps ---
    _group "Control deps" control
    _opt "pygeodesy ($(_ver pygeodesy))"        '_spec pygeodesy'
    _opt "shapely ($(_ver shapely))"            '_spec shapely'
    _opt "geopy ($(_ver geopy))"                '_spec geopy'
    _opt "transforms3d ($(_ver transforms3d))"  '_spec transforms3d'
    _opt "scikit-learn ($(_ver scikit-learn))"  '_spec sklearn'
    _opt "rowan ($(_ver rowan))"                '_spec rowan'

    # --- Vision deps ---
    _group "Vision deps" vision
    _opt "mediapipe ($(_ver mediapipe))"     '_spec mediapipe'
    _opt "depthai / OAK-D ($(_ver depthai))" '_spec depthai'

    # --- Sensors deps ---
    _group "Sensors deps" sensors
    _opt "pyserial ($(_ver pyserial))"   '_spec serial'
    _opt "pymavlink ($(_ver pymavlink))" '_spec pymavlink'

    # --- Interface deps ---
    _group "Interface deps" interface
    _opt "PySide6 ($(_ver PySide6))"     '_spec PySide6'
    _opt "pyqtgraph ($(_ver pyqtgraph))" '_spec pyqtgraph'

    # --- RealSense (Python binding; system libs checked by realsense-verify) ---
    _group "RealSense (Python)" realsense
    _opt "pyrealsense2 ($(_ver pyrealsense2))" '_spec pyrealsense2'

    # --- AI / PyTorch ---
    _group "AI / PyTorch" ai
    if [[ "$_active" == "1" ]]; then
        if _spec torch; then
            local _tv; _tv="$(_ver torch)"

            _req "torch ($_tv) import"                'python3 -c "import torch"'
            _opt "torchvision ($(_ver torchvision))"  '_spec torchvision'
            # Run the GPU check whenever torch is a CUDA build. Jetson wheels are
            # versioned without the "+cuXXX" local tag, so key off
            # torch.version.cuda rather than the version string.
            if python3 -c "import torch,sys; sys.exit(0 if torch.version.cuda else 1)" 2>/dev/null; then
                # Single torch import does is_available + GPU tensor + device name.
                local _gpu
                if _gpu=$(python3 -c "import torch; assert torch.cuda.is_available(); assert torch.randn(2,2).cuda().is_cuda; print(torch.cuda.get_device_name(0))" 2>/dev/null); then
                    log_success "torch CUDA + GPU tensor (${_gpu})"; _pass=$((_pass + 1)); _gp=$((_gp + 1))
                else
                    log_warning "torch CUDA not usable on this host (optional)"; _warn=$((_warn + 1)); _gw=$((_gw + 1))
                fi
            else
                log_info "torch ${_tv} (CPU build - GPU checks skipped)"
            fi
            _opt "ultralytics ($(_ver ultralytics))"         '_spec ultralytics'
            _opt "transformers ($(_ver transformers))"       '_spec transformers'
            _opt "supervision ($(_ver supervision))"         '_spec supervision'
            _opt "albumentations ($(_ver albumentations))"   '_spec albumentations'
            _opt "timm ($(_ver timm))"                       '_spec timm'
            _opt "rfdetr ($(_ver rfdetr))"                   '_spec rfdetr'
            _opt "datasets ($(_ver datasets))"               '_spec datasets'
            _opt "huggingface_hub ($(_ver huggingface-hub))" '_spec huggingface_hub'
            _opt "roboflow ($(_ver roboflow))"               '_spec roboflow'
            _opt "accelerate ($(_ver accelerate))"           '_spec accelerate'
            _opt "tensorboard ($(_ver tensorboard))"         '_spec tensorboard'
        else
            log_warning "PyTorch not installed (optional) - AI module disabled"
            _warn=$((_warn + 1)); _gw=$((_gw + 1))
        fi
    fi

    # --- Entry points & nodes (require the workspace overlay to be sourced) ---
    _group "Entry points & nodes" nodes
    _req "node: app.py"                   'grep -q "app.py" <<<"$_execs"'
    _req "node: aruco_node.py"            'grep -q "aruco_node.py" <<<"$_execs"'
    _req "node: camera_publisher_node.py" 'grep -q "camera_publisher_node.py" <<<"$_execs"'
    _req "node: line_detection_node.py"   'grep -q "line_detection_node.py" <<<"$_execs"'
    _req "node: vision_pose_node.py"       'grep -q "vision_pose_node.py" <<<"$_execs"'
    _opt "CLI: nectar-ai"                 'has_command nectar-ai'

    _gsummary

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

cmd_verify_functional() {
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash" 2>/dev/null || true
    [ -f "${WORKSPACE_DIR}/install/local_setup.bash" ] && \
        source "${WORKSPACE_DIR}/install/local_setup.bash" 2>/dev/null || true
    python3 -m nectar.diagnostics "$@"
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
