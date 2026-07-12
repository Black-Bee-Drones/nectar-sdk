#!/bin/bash
# Per-drone driver installation: MAVROS, Crazyflie (Crazyswarm2), Bebop.
# Each driver is independent; install only what a given drone needs.

_source_ros_ws() {
    source "/opt/ros/${ROS_DISTRO}/setup.bash" 2>/dev/null || true
    [ -f "${WORKSPACE_DIR}/install/setup.bash" ] && \
        source "${WORKSPACE_DIR}/install/setup.bash" 2>/dev/null || true
}

_drone_activation_hint() {
    log_info "To use it now:  source ${WORKSPACE_DIR}/install/setup.bash"
    log_info "New terminals pick it up automatically (configured in ~/.bashrc)."
}

# Run a driver install function; abort on failure
_drone_install_required() {
    local fn="$1"
    if ! "$fn"; then
        log_error "Required driver install failed: ${fn#_}"
        return 1
    fi
}

# Run a driver install function; log and continue on failure
_drone_install_optional() {
    local fn="$1"
    local label="$2"
    if ! "$fn"; then
        log_warning "Skipping ${label} on ${ROS_DISTRO} (optional; install failed or unsupported)"
        return 0
    fi
}

# MAVROS + GeographicLib datasets (ArduPilot / PX4 over ROS).
_drone_mavros() {
    log_section "INSTALLING MAVROS DRIVER"
    SUDO apt-get update
    SUDO apt-get install -y --no-install-recommends \
        "ros-${ROS_DISTRO}-mavros" "ros-${ROS_DISTRO}-mavros-extras"
    cmd_geographiclib
    _source_ros_ws
    log_success "MAVROS driver installed"
    _drone_activation_hint
}

# PX4 over MAVROS. PX4 reuses the MAVROS stack (launched with px4.launch);
# the only difference from ArduPilot is the launch file and flight semantics.
_drone_px4() {
    log_section "INSTALLING PX4 DRIVER (MAVROS)"
    _drone_mavros
    log_info "PX4 uses the MAVROS driver via px4.launch."
    log_info "Connect to a PX4 FCU/SITL with:"
    log_info "  ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580"
    log_info "For PX4 SITL + Gazebo, see: make sim-install FIRMWARE=px4 (scripts/simulation/install_px4.sh)"
    log_info "For the native uXRCE-DDS path (drone 'px4_dds'), run: make drone-px4-dds"
}

# PX4 native uXRCE-DDS (drone 'px4_dds')
_drone_px4_dds() {
    log_section "INSTALLING PX4 NATIVE uXRCE-DDS (px4_msgs + agent)"
    bash "${PROJECT_DIR}/scripts/simulation/install_px4_dds.sh"
    _source_ros_ws
    _drone_activation_hint
}

_crazyflie_build_from_source() {
    local dest="${WORKSPACE_DIR}/src/crazyswarm2"
    mkdir -p "${WORKSPACE_DIR}/src"

    if [ -d "$dest" ]; then
        log_info "crazyswarm2 already present at ${dest}, skipping clone"
    else
        log_info "Cloning Crazyswarm2 from ${CRAZYSWARM2_REPO}..."
        if [ -n "${CRAZYSWARM2_REF}" ]; then
            git clone --recursive -b "${CRAZYSWARM2_REF}" "${CRAZYSWARM2_REPO}" "$dest"
        else
            git clone --recursive "${CRAZYSWARM2_REPO}" "$dest"
        fi
    fi

    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    [ -f install/setup.bash ] && source install/setup.bash

    log_info "Installing Crazyswarm2 rosdep dependencies..."
    rosdep install --from-paths src --ignore-src -y -r

    log_info "Building Crazyswarm2 (crazyflie, crazyflie_interfaces)..."
    colcon build --symlink-install --packages-up-to crazyflie crazyflie_interfaces \
        --cmake-args -DCMAKE_BUILD_TYPE=Release
}

# Crazyswarm2 (Crazyflie 2.x). Prefer apt binaries; fall back to source build.
_drone_crazyflie() {
    log_section "INSTALLING CRAZYFLIE DRIVER (Crazyswarm2)"
    SUDO apt-get update

    local candidate
    candidate=$(apt-cache policy "ros-${ROS_DISTRO}-crazyflie" 2>/dev/null \
        | awk '/Candidate:/{print $2}')

    if [[ -n "$candidate" && "$candidate" != "(none)" ]]; then
        log_info "Installing Crazyswarm2 from apt (${candidate})..."
        SUDO apt-get install -y --no-install-recommends "${CRAZYFLIE_PACKAGES[@]}"
    else
        log_warning "No apt binary for ros-${ROS_DISTRO}-crazyflie; building from source..."
        _crazyflie_build_from_source
    fi

    # rowan: used by CrazyflieDrone full-state streaming. Pin numpy<2 alongside it
    # so the venv stays cv_bridge-ABI compatible (cv_bridge links against numpy<2).
    _ensure_venv && uv pip install --python "$NECTAR_VENV/bin/python" "rowan>=1.3.0" "numpy>=1.26,<2.0" \
        || log_warning "rowan install skipped"

    _crazyflie_udev

    _source_ros_ws
    if ros2 pkg list 2>/dev/null | grep -qx "crazyflie"; then
        log_success "Crazyflie driver installed (crazyflie on ROS path)"
    else
        log_error "Crazyflie driver not on ROS path after install"
        return 1
    fi
    log_info "Next: set your radio URI in crazyflies.yaml — see"
    log_info "  nectar/nectar/control/crazyflie/README.md (Installation, step 3)"
    _drone_activation_hint
}

# Crazyradio USB permissions: plugdev group + udev rules (Bitcraze vendor 1915).
_crazyflie_udev() {
    log_info "Configuring Crazyradio USB permissions (udev)..."
    getent group plugdev >/dev/null || SUDO groupadd plugdev || true
    SUDO usermod -a -G plugdev "${USER:-root}" || true
    cat <<'EOF' | SUDO tee /etc/udev/rules.d/99-bitcraze.rules >/dev/null
SUBSYSTEM=="usb", ATTRS{idVendor}=="1915", ATTRS{idProduct}=="7777", MODE="0664", GROUP="plugdev"
SUBSYSTEM=="usb", ATTRS{idVendor}=="1915", ATTRS{idProduct}=="0101", MODE="0664", GROUP="plugdev"
EOF
    # Reloading needs a running udevd (absent in containers/at image build time).
    if command -v udevadm >/dev/null 2>&1; then
        SUDO udevadm control --reload-rules 2>/dev/null || true
        SUDO udevadm trigger 2>/dev/null || true
    fi
    log_success "Crazyradio udev rules installed (log out/in for group change)"
}

# Parrot dragon_build (and ArduPilot prereqs) refuse euid 0. Create a passwordless
# sudo build user for Docker/CI; bare-metal non-root installs skip this.
_ensure_build_user() {
    local user="${NECTAR_BUILD_USER:-nectar}"
    if ! command -v sudo >/dev/null 2>&1; then
        apt-get update && apt-get install -y --no-install-recommends sudo
    fi
    if ! id -u "${user}" >/dev/null 2>&1; then
        useradd -m -s /bin/bash "${user}"
    fi
    if [ ! -f "/etc/sudoers.d/90-${user}-nectar" ]; then
        echo "${user} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${user}-nectar"
        chmod 0440 "/etc/sudoers.d/90-${user}-nectar"
    fi
    echo "${user}"
}

# Run colcon as a non-root
_bebop_colcon_build() {
    local target="$1"
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        colcon build --packages-up-to "${target}" --symlink-install
        return
    fi

    local user
    user="$(_ensure_build_user)"
    log_info "Parrot ARSDK refuses root; building ${target} as '${user}'..."
    mkdir -p "${WORKSPACE_DIR}/build" "${WORKSPACE_DIR}/install" "${WORKSPACE_DIR}/log"
    chown -R "${user}:${user}" \
        "${WORKSPACE_DIR}/src/ros2_parrot_arsdk" \
        "${WORKSPACE_DIR}/src/ros2_bebop_driver" \
        "${WORKSPACE_DIR}/build" \
        "${WORKSPACE_DIR}/install" \
        "${WORKSPACE_DIR}/log"

    sudo -u "${user}" -H env ROS_DISTRO="${ROS_DISTRO}" WORKSPACE_DIR="${WORKSPACE_DIR}" \
        bash -c '
            set -eo pipefail
            git config --global color.ui auto
            # ROS setup.bash references unset vars; nounset must stay off around source.
            set +u
            source "/opt/ros/${ROS_DISTRO}/setup.bash"
            cd "${WORKSPACE_DIR}"
            [ -f install/setup.bash ] && source install/setup.bash
            set -u
            colcon build --packages-up-to "'"${target}"'" --symlink-install
        '
}

# Bebop 2 driver (jeremyfix ros2_parrot_arsdk + ros2_bebop_driver, built from source).
_drone_bebop() {
    log_section "INSTALLING BEBOP DRIVER (ros2_bebop_driver)"
    SUDO apt-get update
    SUDO apt-get install -y --no-install-recommends "${BEBOP_APT_PACKAGES[@]}"

    # The ARSDK build invokes Google's `repo` tool, which blocks colcon on a
    # color-output prompt unless this is set first.
    git config --global color.ui auto

    mkdir -p "${WORKSPACE_DIR}/src"
    local entry name url
    for entry in "${BEBOP_REPOS[@]}"; do
        name="${entry%%=*}"
        url="${entry#*=}"
        if [ -d "${WORKSPACE_DIR}/src/${name}" ]; then
            log_info "${name} already present, skipping clone"
        else
            log_info "Cloning ${name}..."
            git clone "$url" "${WORKSPACE_DIR}/src/${name}"
        fi
    done

    _bebop_patch_ffmpeg

    cd "$WORKSPACE_DIR"
    source "/opt/ros/${ROS_DISTRO}/setup.bash"

    log_info "Installing Bebop rosdep dependencies..."
    rosdep install --from-paths \
        src/ros2_parrot_arsdk src/ros2_bebop_driver \
        --ignore-src -y -r \
        || log_warning "rosdep install reported issues; continuing with apt packages"

    log_info "Building ros2_parrot_arsdk (ARSDK 3.14.0, takes a few minutes)..."
    _bebop_colcon_build ros2_parrot_arsdk
    source install/setup.bash

    log_info "Building ros2_bebop_driver..."
    _bebop_colcon_build ros2_bebop_driver

    _source_ros_ws
    if ros2 pkg list 2>/dev/null | grep -qx "ros2_bebop_driver"; then
        log_success "Bebop driver built (ros2_bebop_driver on ROS path)"
    else
        log_warning "Bebop driver built but not on ROS path — check colcon output above"
        return 1
    fi
    log_info "Launch: ros2 launch ros2_bebop_driver bebop_node_launch.xml ip:=192.168.42.1"
    _drone_activation_hint
}

# ros2_bebop_driver targets FFmpeg 4; on FFmpeg 5/6 (Ubuntu 24.04)
# avcodec_find_decoder() returns const AVCodec*. Make the member match.
# Idempotent: only the non-const declaration matches.
_bebop_patch_ffmpeg() {
    local hpp="${WORKSPACE_DIR}/src/ros2_bebop_driver/include/ros2_bebop_driver/video_decoder.hpp"
    [ -f "$hpp" ] || return 0
    if grep -qE '^[[:space:]]*AVCodec \*p_codec_' "$hpp"; then
        log_info "Patching ros2_bebop_driver for FFmpeg 5/6 (const AVCodec*)..."
        sed -i 's/^\([[:space:]]*\)AVCodec \*p_codec_/\1const AVCodec *p_codec_/' "$hpp"
    fi
}

# Full published-image set: required backends first, then best-effort optional ones.
_drone_all() {
    _drone_install_required _drone_mavros
    _drone_install_required _drone_crazyflie
    _drone_install_optional _drone_bebop "Bebop"
    _drone_install_optional _drone_px4_dds "PX4 uXRCE-DDS"
}

# Dispatcher: ./setup.sh drone <mavros|crazyflie|bebop|all>
cmd_drone() {
    local kind="${1:-}"
    case "$kind" in
        mavros)            _drone_mavros ;;
        px4)               _drone_px4 ;;
        px4-dds|px4_dds)   _drone_px4_dds ;;
        crazyflie)         _drone_crazyflie ;;
        bebop)             _drone_bebop ;;
        all)               _drone_all ;;
        ""|list)
            echo "Usage: ./setup.sh drone <type>"
            echo "  types: mavros, px4, px4-dds, crazyflie, bebop, all"
            echo "  all:   mavros + crazyflie (required), bebop + px4-dds (best-effort)"
            ;;
        *)
            log_error "Unknown drone type: $kind (expected mavros|px4|px4-dds|crazyflie|bebop|all)"
            return 1
            ;;
    esac
}
