#!/bin/bash

# Intel RealSense installation
# Builds librealsense from source with optional CUDA support
# installs realsense-ros and vision_to_mavros

_check_cuda() {
    USE_CUDA=false
    NVCC_PATH=""

    if [[ "${REALSENSE_CUDA:-}" == "false" ]]; then
        log_info "REALSENSE_CUDA=false — building without CUDA"
        return
    fi

    if has_command nvcc; then
        USE_CUDA=true
        NVCC_PATH=$(which nvcc)
        log_success "CUDA found in PATH: $(nvcc --version | grep 'release' | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')"

    elif [ -f /usr/local/cuda/bin/nvcc ]; then
        USE_CUDA=true
        NVCC_PATH="/usr/local/cuda/bin/nvcc"
        export PATH=/usr/local/cuda/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}
        log_success "CUDA found at /usr/local/cuda: $($NVCC_PATH --version | grep 'release' | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')"

    elif has_command nvidia-smi; then
        for cuda_dir in /usr/local/cuda-12* /usr/local/cuda-11*; do
            if [ -f "$cuda_dir/bin/nvcc" ]; then
                USE_CUDA=true
                NVCC_PATH="$cuda_dir/bin/nvcc"
                export PATH=$cuda_dir/bin:$PATH
                export LD_LIBRARY_PATH=$cuda_dir/lib64:${LD_LIBRARY_PATH:-}
                log_success "CUDA found at $cuda_dir: $($NVCC_PATH --version | grep 'release' | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')"
                break
            fi
        done
        if [[ "$USE_CUDA" != "true" ]]; then
            log_warning "nvidia-smi found but nvcc not located. CUDA may be partially installed."
        fi
    else
        log_warning "CUDA not found. Building without CUDA support."
    fi

    if [[ "$USE_CUDA" == "true" ]]; then
        if ! $NVCC_PATH --version &> /dev/null; then
            log_error "CUDA found but nvcc is not working."
            USE_CUDA=false
        fi
    fi
}

# installation checks 

_check_existing_realsense() {
    EXISTING_LIBREALSENSE=false
    EXISTING_ROS_LIBREALSENSE=false
    EXISTING_REALSENSE_ROS=false

    if [ -d "$HOME/librealsense" ]; then
        local ver
        ver=$(cd "$HOME/librealsense" && git describe --tags 2>/dev/null || echo "unknown")
        log_info "librealsense source found: $ver"
        EXISTING_LIBREALSENSE=true
    fi

    if pkg-config --exists librealsense2 2>/dev/null; then
        log_info "librealsense2 (pkg-config): $(pkg-config --modversion librealsense2)"
    fi

    if dpkg -l 2>/dev/null | grep -q "ros-${ROS_DISTRO}-librealsense2"; then
        local rv
        rv=$(dpkg -l | grep "ros-${ROS_DISTRO}-librealsense2" | awk '{print $3}')
        log_warning "ros-${ROS_DISTRO}-librealsense2 (apt) found: $rv"
        EXISTING_ROS_LIBREALSENSE=true
    fi

    if [ -d "${WORKSPACE_DIR}/src/realsense-ros" ]; then
        local tag
        tag=$(cd "${WORKSPACE_DIR}/src/realsense-ros" && git describe --tags 2>/dev/null || git rev-parse --short HEAD || echo "unknown")
        log_info "realsense-ros found: $tag"
        EXISTING_REALSENSE_ROS=true
    fi

    if has_command rs-enumerate-devices; then
        log_info "rs-enumerate-devices: $(rs-enumerate-devices --version | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)"
    fi
}

# Remove conflicting installations 

_remove_conflicting_realsense() {
    log_section "REMOVING CONFLICTING INSTALLATIONS"

    if dpkg -l 2>/dev/null | grep -q "ros-${ROS_DISTRO}-librealsense2"; then
        log_warning "ros-${ROS_DISTRO}-librealsense2 apt packages found. Removing..."
        SUDO apt-get remove -y "ros-${ROS_DISTRO}-librealsense2"* || true
        SUDO apt-get autoremove -y || true
        log_success "ros-${ROS_DISTRO}-librealsense2 removed"
    fi

    if [[ "$EXISTING_LIBREALSENSE" == "true" ]]; then
        if [[ "${NON_INTERACTIVE:-}" != "true" ]]; then
            read -p "Reinstall librealsense ${LIBREALSENSE_VERSION}? (Y/n): " -n 1 -r && echo
            if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then return; fi
        fi
        log_info "Removing previous librealsense..."
        cd "$HOME/librealsense"
        [ -d build ] && (cd build && SUDO make uninstall 2>/dev/null || true)
        cd "$HOME" && rm -rf librealsense
        EXISTING_LIBREALSENSE=false
    fi

    if [[ "$EXISTING_REALSENSE_ROS" == "true" ]]; then
        if [[ "${NON_INTERACTIVE:-}" != "true" ]]; then
            read -p "Reinstall realsense-ros ${REALSENSE_ROS_TAG}? (Y/n): " -n 1 -r && echo
            if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then return; fi
        fi
        log_info "Removing previous realsense-ros..."
        rm -rf "${WORKSPACE_DIR}/src/realsense-ros"
        EXISTING_REALSENSE_ROS=false
    fi
}

# system dependencies 

_install_realsense_deps() {
    log_section "INSTALLING REALSENSE SYSTEM DEPENDENCIES"
    SUDO apt-add-repository universe -y 2>/dev/null || true
    SUDO apt-get update
    SUDO apt-get install -y "${REALSENSE_SYSTEM_PACKAGES[@]}"

    if [[ "$USE_CUDA" == "true" ]]; then
        log_info "Installing CUDA OpenGL libraries..."
        SUDO apt-get install -y "${REALSENSE_CUDA_PACKAGES[@]}"
    fi
    log_success "RealSense dependencies installed"
}

# Build librealsense from source 

_build_librealsense() {
    log_section "BUILDING LIBREALSENSE ${LIBREALSENSE_VERSION}"

    local rs_dir="${HOME}/librealsense"

    if [[ "$EXISTING_LIBREALSENSE" == "true" ]]; then
        local cur
        cur=$(cd "$rs_dir" && git describe --tags 2>/dev/null || echo "unknown")
        if [[ "$cur" == "$LIBREALSENSE_VERSION" ]]; then
            log_info "librealsense ${LIBREALSENSE_VERSION} already installed"
            return 0
        fi
    fi

    if [ ! -d "$rs_dir" ]; then
        log_info "Cloning librealsense..."
        cd "$HOME"
        git clone https://github.com/IntelRealSense/librealsense.git
    fi

    cd "$rs_dir"
    [ -d build ] && rm -rf build
    git fetch --tags

    if ! git tag -l | grep -q "^${LIBREALSENSE_VERSION}$"; then
        log_error "Version ${LIBREALSENSE_VERSION} not found!"
        git tag -l | grep "^v2\." | tail -10
        exit 1
    fi

    git checkout "$LIBREALSENSE_VERSION"
    log_success "Checked out: $(git describe --tags)"

    mkdir -p build && cd build

    local cmake_args=(
        -DBUILD_EXAMPLES=true
        -DFORCE_RSUSB_BACKEND=true
        -DCMAKE_BUILD_TYPE=release
        -DBUILD_PYTHON_BINDINGS=ON
        "-DPYTHON_EXECUTABLE=$(which python3)"
    )

    if [[ "$USE_CUDA" == "true" ]]; then
        log_info "Configuring with CUDA support..."
        export CUDACXX="$NVCC_PATH"
        cmake_args+=("-DBUILD_WITH_CUDA=true")
    else
        cmake_args+=("-DBUILD_WITH_CUDA=false")
    fi

    cmake ../ "${cmake_args[@]}"

    log_info "Building librealsense (this may take a while)..."
    if ! make -j"$(nproc)"; then
        log_warning "Parallel build failed, retrying single-threaded..."
        make || { log_error "Build failed!"; exit 1; }
    fi

    SUDO make install
    SUDO ldconfig

    # PYTHONPATH for pyrealsense2
    if ! grep -Fxq 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib' ~/.bashrc; then
        echo 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib' >> ~/.bashrc
        log_success "PYTHONPATH added to ~/.bashrc"
    fi

    # udev rules 
    cd "$rs_dir"
    SUDO mkdir -p /etc/udev/rules.d/ 2>/dev/null || true
    SUDO cp config/99-realsense-libusb.rules /etc/udev/rules.d/ 2>/dev/null || true
    SUDO udevadm control --reload-rules 2>/dev/null && SUDO udevadm trigger 2>/dev/null || true

    log_success "librealsense ${LIBREALSENSE_VERSION} installed"
}

# Install realsense-ros 

_install_realsense_ros() {
    log_section "INSTALLING REALSENSE-ROS (tag: ${REALSENSE_ROS_TAG})"

    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_error "ROS2 workspace not found at ${WORKSPACE_DIR}"
        exit 1
    fi

    cd "${WORKSPACE_DIR}/src"

    if [[ "$EXISTING_REALSENSE_ROS" == "true" ]]; then
        local cur
        cur=$(cd realsense-ros && git describe --tags 2>/dev/null || echo "")
        if [[ "$cur" == "$REALSENSE_ROS_TAG" ]]; then
            log_info "realsense-ros ${REALSENSE_ROS_TAG} already installed"
            return 0
        fi
    fi

    if [ ! -d "realsense-ros" ]; then
        git clone https://github.com/IntelRealSense/realsense-ros.git
    fi

    cd realsense-ros
    git fetch --tags origin
    if git tag -l | grep -q "^${REALSENSE_ROS_TAG}$"; then
        git checkout "${REALSENSE_ROS_TAG}" || git checkout "tags/${REALSENSE_ROS_TAG}"
        log_success "realsense-ros set to tag ${REALSENSE_ROS_TAG}"
    else
        log_error "Tag ${REALSENSE_ROS_TAG} not found!"
        git tag -l | tail -20
        exit 1
    fi
}

# Install vision_to_mavros 

_install_vision_to_mavros() {
    log_section "INSTALLING VISION_TO_MAVROS"

    cd "${WORKSPACE_DIR}/src"
    if [ ! -d "vision_to_mavros" ]; then
        git clone https://github.com/Black-Bee-Drones/vision_to_mavros.git
    else
        cd vision_to_mavros && git pull origin main && cd ..
    fi
    log_success "vision_to_mavros ready"
}

# Rebuild workspace with RealSense 

_rebuild_workspace_realsense() {
    log_section "REBUILDING WORKSPACE"
    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    rosdep update
    rosdep install -i --from-path src --rosdistro "$ROS_DISTRO" --skip-keys=librealsense2 -y
    rm -rf build/ install/ log/
    colcon build --symlink-install
    log_success "Workspace rebuilt"
}

# Verify installation 

_verify_realsense() {
    log_section "VERIFYING REALSENSE INSTALLATION"

    local found=false

    if pkg-config --exists librealsense2 2>/dev/null; then
        local v
        v=$(pkg-config --modversion librealsense2)
        log_success "librealsense2 (pkg-config): $v"
        found=true
    fi

    if has_command rs-enumerate-devices; then
        local rv
        rv=$(rs-enumerate-devices --version | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
        log_success "rs-enumerate-devices: $rv"
        found=true
    fi

    if [ -f "/usr/local/lib/librealsense2.so" ] || \
       [ -f "/usr/lib/x86_64-linux-gnu/librealsense2.so" ] || \
       [ -f "/usr/lib/aarch64-linux-gnu/librealsense2.so" ]; then
        log_success "librealsense2 library found"
        found=true
    fi

    [[ "$found" == "false" ]] && log_error "librealsense2 not found!"

    if dpkg -l 2>/dev/null | grep -q "ros-${ROS_DISTRO}-librealsense2"; then
        log_warning "ros-${ROS_DISTRO}-librealsense2 apt package still installed (may conflict)"
    fi

    source "/opt/ros/${ROS_DISTRO}/setup.bash" 2>/dev/null || true
    [ -f "${WORKSPACE_DIR}/install/local_setup.bash" ] && source "${WORKSPACE_DIR}/install/local_setup.bash"

    local pkgs
    pkgs=$(ros2 pkg list 2>/dev/null || true)
    echo "$pkgs" | grep -q "realsense2_camera" && log_success "realsense2_camera: OK" || log_warning "realsense2_camera: not found"
    echo "$pkgs" | grep -q "vision_to_mavros"  && log_success "vision_to_mavros: OK"  || log_warning "vision_to_mavros: not found"

    log_success "RealSense verification complete"
}

# Public commands 

cmd_realsense() {
    check_not_root
    log_section "REALSENSE INSTALLATION"
    log_info "librealsense: ${LIBREALSENSE_VERSION}  |  realsense-ros: ${REALSENSE_ROS_TAG}"

    _check_cuda
    _check_existing_realsense

    if [[ "${NON_INTERACTIVE:-}" == "true" ]]; then
        # Non-interactive: full install
        _remove_conflicting_realsense
        _install_realsense_deps
        _build_librealsense
        _install_realsense_ros
        _install_vision_to_mavros
        _rebuild_workspace_realsense
        _verify_realsense
        return
    fi

    echo ""
    echo "Select option:"
    echo "1) Full installation (recommended)"
    echo "2) Custom installation"
    echo "3) Verify installation only"
    echo "4) Remove conflicting installations"
    read -p "Option [1]: " option
    option=${option:-1}

    case $option in
        1)
            _remove_conflicting_realsense
            _install_realsense_deps
            _build_librealsense
            _install_realsense_ros
            _install_vision_to_mavros
            _rebuild_workspace_realsense
            _verify_realsense
            ;;
        2)
            echo "Select steps (space-separated, e.g., 1 3 5):"
            echo "1) Remove conflicts   2) System deps   3) Build librealsense"
            echo "4) realsense-ros      5) vision_to_mavros   6) Rebuild workspace"
            echo "7) Verify"
            read -p "Steps: " steps
            for step in $steps; do
                case $step in
                    1) _remove_conflicting_realsense ;; 2) _install_realsense_deps ;;
                    3) _build_librealsense ;; 4) _install_realsense_ros ;;
                    5) _install_vision_to_mavros ;; 6) _rebuild_workspace_realsense ;;
                    7) _verify_realsense ;; *) log_warning "Invalid step: $step" ;;
                esac
            done
            ;;
        3) _verify_realsense ;;
        4) _remove_conflicting_realsense ;;
        *) log_error "Invalid option"; exit 1 ;;
    esac

    if [[ "$USE_CUDA" == "true" ]] && ! has_command nvcc; then
        log_warning "CUDA was used but is not in PATH permanently."
        log_info "Add to ~/.bashrc: export PATH=/usr/local/cuda/bin:\$PATH"
    fi
}

cmd_realsense_verify() {
    _check_existing_realsense
    _verify_realsense
}
