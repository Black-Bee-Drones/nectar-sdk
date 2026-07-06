#!/bin/bash
# =============================================================================
# SDK Setup - Unified CLI for installation, build, and development.
#
# Usage:
#   ./setup.sh              Guided setup
#   ./setup.sh <command>    Run a specific command
#   ./setup.sh help         Show all available commands
#
# Environment variables:
#   ROS2_WORKSPACE    Override auto-detected workspace path
#   NON_INTERACTIVE   Set to "true" to skip prompts (for Docker/CI)
# =============================================================================

set -e

# Source all modules
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/config.sh"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/system.sh"
source "$SCRIPT_DIR/lib/ros2.sh"
source "$SCRIPT_DIR/lib/python.sh"
source "$SCRIPT_DIR/lib/workspace.sh"
source "$SCRIPT_DIR/lib/drones.sh"
source "$SCRIPT_DIR/lib/git.sh"
source "$SCRIPT_DIR/lib/realsense.sh"
source "$SCRIPT_DIR/lib/simulation.sh"
source "$SCRIPT_DIR/lib/driver.sh"

show_help() {
    echo ""
    echo -e "${PURPLE}  SDK Setup - Installation & Development CLI${NC}"
    echo -e "${PURPLE}  ===========================================${NC}"
    echo ""
    echo -e "${BLUE}Choose your path (by starting state):${NC}"
    echo "  Fresh machine (no ROS 2):     make full-install     ROS 2 + deps + build, from zero"
    echo "  Have ROS 2 + this repo:       make setup            Opens the setup menu (configure anything)"
    echo "  Containers (no host setup):   make docker-build && make docker-run"
    echo "  (running ./setup.sh with no command opens the same menu)"
    echo ""
    echo -e "${BLUE}Common goals:${NC}"
    echo "  PX4 over uXRCE-DDS + detection:  make setup (pick 'control ai') && make drone-px4-dds"
    echo "  ArduPilot / PX4 over MAVROS:     make setup (pick 'control')    && make drone-mavros"
    echo "  GUI app only:                    make python-interface"
    echo "  Simulation (SITL + Gazebo):      see 'Simulation' below"
    echo ""
    echo -e "${BLUE}System:${NC}"
    echo "  ./setup.sh system             Install system packages (apt; skips if already present, FORCE=1 to re-run)"
    echo "  ./setup.sh update             Update system (apt upgrade)"
    echo "  ./setup.sh git-ssh            Configure git and SSH keys"
    echo "  ./setup.sh git-lfs            Install and initialize Git LFS"
    echo ""
    echo -e "${BLUE}ROS2:${NC}"
    echo "  ./setup.sh ros2               Install ROS2 ${ROS_DISTRO^} + MAVROS"
    echo "  ./setup.sh ros2-env           Configure ROS2 in ~/.bashrc"
    echo "  ./setup.sh rosdep-init        Initialize rosdep"
    echo "  ./setup.sh geographiclib      MAVROS geoid datasets (also run by 'drone mavros'; skips if present)"
    echo ""
    echo -e "${BLUE}Drone drivers:${NC}"
    echo "  ./setup.sh drone mavros       MAVROS (ArduPilot/PX4 over ROS) + GeographicLib"
    echo "  ./setup.sh drone px4          PX4 over MAVROS (reuses MAVROS, px4.launch)"
    echo "  ./setup.sh drone px4-dds      PX4 native uXRCE-DDS: px4_msgs + Micro XRCE-DDS Agent"
    echo "  ./setup.sh drone crazyflie    Crazyswarm2 (Crazyflie 2.x)"
    echo "  ./setup.sh drone bebop        Bebop driver (ros2_bebop_driver + ARSDK)"
    echo "  ./setup.sh drone all          mavros + crazyflie + bebop"
    echo ""
    echo -e "${BLUE}Python Dependencies (into the shared uv venv; 'make python-<x>' also works):${NC}"
    echo "  ./setup.sh python             core only (numpy / opencv / scipy)"
    echo "  ./setup.sh python control     core + control (navigation / PID / GPS)"
    echo "  ./setup.sh python vision      core + vision (cameras / ArUco / MediaPipe)"
    echo "  ./setup.sh python ai          core + AI (YOLO / DETR / RF-DETR); run pytorch too"
    echo "  ./setup.sh python interface   core + Qt6 GUI"
    echo "  ./setup.sh python sensors     core + rangefinder / MAVLink bridge"
    echo "  ./setup.sh python all         all modules (no AI)            [make python-all]"
    echo "  ./setup.sh python full        everything (all + AI)          [make python-full]"
    echo "  ./setup.sh pytorch            PyTorch (auto-detect CUDA; cpu / cu124 to force)"
    echo ""
    echo -e "${BLUE}Workspace:${NC}"
    echo "  ./setup.sh clone              Clone project into workspace"
    echo "  ./setup.sh ros2-deps          Install ROS2 package deps (rosdep)"
    echo "  ./setup.sh build              Build entire workspace"
    echo "  ./setup.sh build-pkg          Build SDK packages only"
    echo "  ./setup.sh clean              Clean build artifacts"
    echo "  ./setup.sh verify             Verify installation (presence/imports)"
    echo "  ./setup.sh verify-functional  Functional regression tests (pytest; self-skip w/o hw)"
    echo "  ./setup.sh verify-hardware    Hardware-gated tests (opt-in; needs devices attached)"
    echo "  ./setup.sh verify-sitl        SITL flight tests in a headless sim (opt-in; needs sim stack)"
    echo "  ./setup.sh doctor             Environment report (ROS, modules, devices, CUDA)"
    echo "  ./setup.sh test               Run colcon test (functional suite + lint)"
    echo "  ./setup.sh ci-local           Build+verify each ROS distro image locally (DISTROS=, FULL=1)"
    echo ""
    echo -e "${BLUE}Hardware:${NC}"
    echo "  ./setup.sh realsense          Install Intel RealSense D435i"
    echo "  ./setup.sh realsense-verify   Verify RealSense installation"
    echo ""
    echo -e "${BLUE}Docker:${NC}"
    echo "  ./setup.sh docker-build       Build SDK image (no AI, fast)"
    echo "  ./setup.sh docker-build-full  Build full image (+ PyTorch + AI)"
    echo "  ./setup.sh docker-build-t265  Build SDK image with T265 support (librealsense v2.53.1)"
    echo "  ./setup.sh docker-publish-jetson  Verify + push the Jetson image to Docker Hub (run on Jetson)"
    echo "  ./setup.sh docker-run         Run container (selects image, GPU auto)"
    echo "  ./setup.sh docker-exec        Open new shell in running container"
    echo "    On Jetson, build/run auto-use Dockerfile.jetson (:jetson tags) and --runtime nvidia"
    echo ""
    echo -e "${BLUE}Simulation (FIRMWARE=ardupilot|px4  ENV=outdoor|indoor  PROTOCOL=mavros|mavlink):${NC}"
    echo "  ./setup.sh sim-install --firmware F   Install SITL + Gazebo (ardupilot|px4|all)"
    echo "  ./setup.sh sim-start --firmware F --env E    Terminal 1: start the simulator"
    echo "  ./setup.sh sim-bridge --firmware F --env E --protocol P   Terminal 2: ROS stack"
    echo "  ./setup.sh sim-stop                   Stop all simulation processes (both firmwares)"
    echo "    Defaults: ardupilot / outdoor / mavros. PROTOCOL=mavlink is ArduPilot-only;"
    echo "    for PX4 use mavros (or dds for native uXRCE-DDS). Extra tokens pass through."
    echo ""
    echo -e "${BLUE}Real-hardware drivers (start the bridge your mission connects to):${NC}"
    echo "  ./setup.sh driver mavros [--env E]    ArduPilot/PX4 MAVROS (apm.launch); indoor=vision-pose"
    echo "  ./setup.sh driver px4 [--env E]       PX4 over MAVROS (px4.launch)"
    echo "  ./setup.sh driver px4-dds             PX4 native uXRCE-DDS (Micro XRCE-DDS Agent)"
    echo "  ./setup.sh driver mavlink [--env E]   Direct MAVLink (outdoor: none; indoor: vision-pose)"
    echo "  ./setup.sh driver bebop               Bebop driver"
    echo "  ./setup.sh driver crazyflie           Crazyflie server (Crazyswarm2)"
    echo "  ./setup.sh driver-stop                Stop all real-hardware drivers/bridges"
    echo "    env vars: FCU_URL=serial:///dev/ttyUSB0:921600  DEV=/dev/ttyUSB0 BAUD=921600  PORT=8888  IP=192.168.42.1"
    echo ""
    echo -e "${BLUE}Docker env vars:${NC}"
    echo "  ROS_DISTRO=jazzy              Build for different ROS distro"
    echo "  TORCH_VARIANT=cu124           Build full with CUDA PyTorch"
    echo "  TORCH_VARIANT=auto            Auto-detect CUDA from nvidia-smi"
    echo "  TORCH_VERSION=2.7.1           Pin specific torch version"
    echo "  DOCKER_NO_MOUNT=true          Run without local project mount"
    echo ""
    echo -e "${BLUE}Info:${NC}"
    echo "  Workspace:  ${WORKSPACE_DIR}"
    echo "  Project:    ${PROJECT_DIR}"
    echo "  ROS distro: ${ROS_DISTRO}"
    echo ""
}

# Docker

cmd_docker_build() {
    local target="${1:-sdk}"
    local tag_suffix="${2:-}"
    local variant="${TORCH_VARIANT}"

    # Jetson (Tegra): build the dedicated Dockerfile.jetson (L4T base + CUDA
    # wheels), tagged nectar-sdk:jetson / :jetson-full. Auto-detected; the x86
    # distro/torch/realsense build args below do not apply. Override the L4T
    # base or torch index with L4T_TAG / TORCH_INDEX.
    if [ -f /etc/nv_tegra_release ] && [ -z "$tag_suffix" ]; then
        local jtag="${DOCKER_IMAGE_PREFIX}:jetson"
        [[ "$target" == "sdk-full" ]] && jtag="${DOCKER_IMAGE_PREFIX}:jetson-full"
        local jargs=()
        [ -n "${L4T_TAG:-}" ]     && jargs+=(--build-arg "L4T_TAG=${L4T_TAG}")
        [ -n "${TORCH_INDEX:-}" ] && jargs+=(--build-arg "TORCH_INDEX=${TORCH_INDEX}")
        jargs+=(--build-arg "INSTALL_REALSENSE=${INSTALL_REALSENSE:-false}")
        jargs+=(--build-arg "REALSENSE_CUDA=${REALSENSE_CUDA:-false}")
        [ -n "${INSTALL_DRONE:-}" ] && jargs+=(--build-arg "INSTALL_DRONE=${INSTALL_DRONE}")
        [ -n "${INSTALL_SIM:-}" ] && jargs+=(--build-arg "INSTALL_SIM=${INSTALL_SIM}")
        [ -n "${LIBREALSENSE_VERSION:-}" ] && jargs+=(--build-arg "LIBREALSENSE_VERSION=${LIBREALSENSE_VERSION}")
        [ -n "${REALSENSE_ROS_TAG:-}" ]    && jargs+=(--build-arg "REALSENSE_ROS_TAG=${REALSENSE_ROS_TAG}")
        log_info "Jetson detected — building $jtag from Dockerfile.jetson (target=$target, realsense=${INSTALL_REALSENSE:-false}, realsense_cuda=${REALSENSE_CUDA:-false})"
        docker build --network=host \
            "${jargs[@]}" \
            --target "$target" \
            -t "$jtag" \
            -f "${PROJECT_DIR}/docker/Dockerfile.jetson" "$PROJECT_DIR"
        log_success "Docker image $jtag built"
        return
    fi

    if [[ "$target" == "sdk-full" && "$variant" == "auto" ]]; then
        local cuda_ver
        cuda_ver=$(_detect_cuda_version)
        if [[ -n "$cuda_ver" ]]; then
            variant=$(_cuda_to_torch_variant "$cuda_ver")
            log_info "Auto-detected CUDA ${cuda_ver} → ${variant}"
        else
            variant="cpu"
            log_info "No GPU detected → cpu"
        fi
    fi

    local tag="${DOCKER_IMAGE_PREFIX}:${ROS_DISTRO}"
    if [[ "$target" == "sdk-full" ]]; then
        tag="${DOCKER_IMAGE_PREFIX}:${ROS_DISTRO}-full-${variant}"
    fi
    [ -n "$tag_suffix" ] && tag="${DOCKER_IMAGE_PREFIX}:${ROS_DISTRO}-${tag_suffix}"

    local build_args=(
        --build-arg ROS_DISTRO="${ROS_DISTRO}"
        --build-arg TORCH_VARIANT="${variant}"
        --build-arg INSTALL_GAZEBO="${INSTALL_GAZEBO:-false}"
        --build-arg INSTALL_REALSENSE="${INSTALL_REALSENSE:-false}"
        --build-arg REALSENSE_CUDA="${REALSENSE_CUDA:-false}"
        --build-arg INSTALL_DRONE="${INSTALL_DRONE:-}"
    )
    [ -n "${INSTALL_SIM:-}" ] && build_args+=(--build-arg "INSTALL_SIM=${INSTALL_SIM}")
    [ -n "${LIBREALSENSE_VERSION:-}" ] && build_args+=(--build-arg "LIBREALSENSE_VERSION=${LIBREALSENSE_VERSION}")
    [ -n "${REALSENSE_ROS_TAG:-}" ]    && build_args+=(--build-arg "REALSENSE_ROS_TAG=${REALSENSE_ROS_TAG}")

    log_info "Building $tag (target=$target, distro=$ROS_DISTRO, torch=$variant)..."
    docker build --network=host \
        "${build_args[@]}" \
        --target "$target" \
        -t "$tag" \
        -f "${PROJECT_DIR}/docker/Dockerfile" "$PROJECT_DIR"
    log_success "Docker image $tag built"
}

cmd_docker_build_t265() {
    export LIBREALSENSE_VERSION="v2.53.1"
    export REALSENSE_ROS_TAG="4.51.1"
    export INSTALL_REALSENSE="true"
    export ROS_DISTRO="humble"
    cmd_docker_build "sdk" "t265"
}

#   NAMESPACE=<dockerhub-user> VERSION=<release> make docker-publish-jetson
cmd_docker_publish_jetson() {
    local ns="${NAMESPACE:-}"
    local version="${VERSION:-}"
    local target="${TARGET:-sdk-full}"
    local jetpack="${JETPACK:-jp6.2}"

    if [ ! -f /etc/nv_tegra_release ]; then
        log_error "Not a Jetson. The Jetson image must be built and published on a Jetson."
        return 1
    fi
    if [ -z "$ns" ] || [ -z "$version" ]; then
        log_error "Usage: NAMESPACE=<dockerhub-user> VERSION=<release> make docker-publish-jetson"
        log_error "  optional: JETSON_TARGET=sdk|sdk-full (default sdk-full), JETSON_JETPACK=jp6.2"
        return 1
    fi

    local variant="jetson"
    [ "$target" = "sdk-full" ] && variant="jetson-full"
    local local_tag="${DOCKER_IMAGE_PREFIX}:${variant}"

    if ! docker image inspect "$local_tag" >/dev/null 2>&1; then
        log_error "Image $local_tag not found. Build the complete image first:"
        log_error "  INSTALL_REALSENSE=true REALSENSE_CUDA=true make docker-build-full"
        return 1
    fi

    log_section "VERIFYING $local_tag ON THIS JETSON BEFORE PUBLISH"
    log_info "SDK verify..."
    docker run --rm --runtime nvidia "$local_tag" bash -lc \
        'source /opt/ros/$ROS_DISTRO/setup.bash; source /home/ros2_ws/install/local_setup.bash 2>/dev/null; /home/ros2_ws/src/nectar-sdk/scripts/setup.sh verify' \
        || { log_error "SDK verify failed — not publishing"; return 1; }

    if [ "$target" = "sdk-full" ]; then
        log_info "PyTorch CUDA verify..."
        docker run --rm --runtime nvidia "$local_tag" \
            python3 -c 'import torch; assert torch.cuda.is_available(), "CUDA not available"; print("torch", torch.__version__, "CUDA OK")' \
            || { log_error "torch CUDA verify failed — not publishing"; return 1; }
    fi

    log_info "RealSense verify..."
    docker run --rm --runtime nvidia -v /dev/bus/usb:/dev/bus/usb "$local_tag" bash -lc \
        'source /opt/ros/$ROS_DISTRO/setup.bash; source /home/ros2_ws/install/local_setup.bash 2>/dev/null; /home/ros2_ws/src/nectar-sdk/scripts/setup.sh realsense-verify' \
        || { log_error "RealSense verify failed — not publishing"; return 1; }

    local remote="${ns}/${DOCKER_IMAGE_PREFIX}"
    local tags=("${remote}:${variant}-${version}" "${remote}:${variant}-${jetpack}" "${remote}:${variant}")
    log_section "PUSHING ${remote} (${variant}: ${version}, ${jetpack}, latest)"
    log_warning "Requires 'docker login' to have been run for ${ns}."
    local t
    for t in "${tags[@]}"; do
        docker tag "$local_tag" "$t"
        log_info "Pushing $t ..."
        docker push "$t" || { log_error "Push failed for $t (run 'docker login'?)"; return 1; }
    done
    log_success "Published: ${tags[*]}"
}

DOCKER_CONTAINER_PREFIX="${ROS2_PKG_NAME}"

# Find all SDK images available locally
_docker_images() {
    docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null \
        | grep "^${DOCKER_IMAGE_PREFIX}:" \
        | sort
}

# Find all running SDK containers
_docker_running() {
    docker ps --format '{{.Names}}' 2>/dev/null \
        | grep "^${DOCKER_CONTAINER_PREFIX}" \
        | sort
}

_container_name() {
    local tag="$1"
    local suffix="${tag#*:}"
    echo "${DOCKER_CONTAINER_PREFIX}_${suffix}"
}

cmd_docker_run() {
    local images
    mapfile -t images < <(_docker_images)

    if [ ${#images[@]} -eq 0 ]; then
        log_error "No images found. Build first: make docker-build"
        exit 1
    fi

    local tag
    if [ ${#images[@]} -eq 1 ]; then
        tag="${images[0]}"
    elif [[ "${NON_INTERACTIVE:-}" == "true" ]]; then
        tag="${images[0]}"
    else
        echo ""
        echo "Available images:"
        for i in "${!images[@]}"; do
            echo "  $((i+1))) ${images[$i]}"
        done
        echo ""
        read -p "Select [1]: " choice
        choice="${choice:-1}"
        tag="${images[$((choice-1))]}"
    fi

    local name
    name=$(_container_name "$tag")
    docker rm -f "$name" >/dev/null 2>&1 || true
    xhost +local:root 2>/dev/null || true

    local xauth="${XAUTHORITY:-$HOME/.Xauthority}"

    local devices=()
    for dev in /dev/video*; do
        [ -e "$dev" ] && devices+=(--device="$dev:$dev")
    done

    if [ ${#devices[@]} -eq 0 ]; then
        log_warning "No video devices found. Webcam nodes won't work."
    fi

    local gpu_flag=""
    if [ -f /etc/nv_tegra_release ]; then
        gpu_flag="--runtime nvidia"
        log_info "NVIDIA Jetson detected (using --runtime nvidia)"
    elif command -v nvidia-smi &>/dev/null; then
        gpu_flag="--gpus all"
        log_info "NVIDIA GPU detected"
    fi

    local tty_flag="-i"
    [ -t 0 ] && tty_flag="-it"

    local volumes=(
        --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw"
        --volume="$xauth:/root/.Xauthority:rw"
        --volume="/dev:/dev"
    )

    if [[ "${DOCKER_NO_MOUNT:-}" != "true" ]] && [ -d "$PROJECT_DIR" ]; then
        volumes+=(--volume="${PROJECT_DIR}:/home/ros2_ws/src/nectar-sdk")
        log_info "Mounting local project (disable: DOCKER_NO_MOUNT=true)"
    fi

    log_info "Starting container $name ($tag)..."
    log_info "Open more terminals: make docker-exec"
    docker run $tty_flag --rm \
        --name="$name" \
        --env="DISPLAY=$DISPLAY" \
        --env="QT_X11_NO_MITSHM=1" \
        --ipc=host \
        --net=host \
        --privileged \
        $gpu_flag \
        "${volumes[@]}" \
        --device-cgroup-rule='c 81:* rmw' \
        --device-cgroup-rule='c 189:* rmw' \
        "${devices[@]}" \
        "$tag" \
        bash
}

cmd_docker_exec() {
    local containers
    mapfile -t containers < <(_docker_running)

    if [ ${#containers[@]} -eq 0 ]; then
        log_error "No running container. Start first: make docker-run"
        exit 1
    fi

    local name
    if [ ${#containers[@]} -eq 1 ]; then
        name="${containers[0]}"
    elif [[ "${NON_INTERACTIVE:-}" == "true" ]]; then
        name="${containers[0]}"
    else
        echo ""
        echo "Running containers:"
        for i in "${!containers[@]}"; do
            local img
            img=$(docker inspect --format '{{.Config.Image}}' "${containers[$i]}" 2>/dev/null)
            echo "  $((i+1))) ${containers[$i]}  (${img})"
        done
        echo ""
        read -p "Select [1]: " choice
        choice="${choice:-1}"
        name="${containers[$((choice-1))]}"
    fi

    local tty_flag="-i"
    [ -t 0 ] && tty_flag="-it"

    log_info "Attaching to $name..."
    docker exec $tty_flag "$name" bash
}

# Setup (existing ROS2 workspace — guided: pick modules, then build SDK packages)

# Echo the chosen module set (space-separated tokens). Honors NON_INTERACTIVE
# and non-tty stdin (both -> "all"). Prompt text goes to stderr so the captured
# stdout is only the selection.
_select_modules() {
    if [[ "${NON_INTERACTIVE:-}" == "true" ]] || [ ! -t 0 ]; then
        echo "all"
        return
    fi
    {
        echo ""
        echo "Which modules do you want? (space-separated, e.g. 'control ai')"
        echo "  control    drone navigation / PID / GPS"
        echo "  vision     cameras, ArUco, color, line, MediaPipe"
        echo "  ai         YOLO / DETR / RF-DETR  (+ PyTorch)"
        echo "  interface  Qt6 GUI"
        echo "  sensors    rangefinder / MAVLink bridge"
        echo "  ----------"
        echo "  all        everything except AI   (default)"
        echo "  full       all + AI"
        echo "  core       minimal (numpy / opencv / scipy)"
    } >&2
    local sel
    read -r -p "Modules [all]: " sel
    echo "${sel:-all}"
}

# Install the selected module set. When AI is requested, PyTorch is installed
# first so the AI extras pin to the chosen torch (CUDA auto-detected).
_install_modules() {
    local mods="$*"
    if [[ " $mods " == *" ai "* || " $mods " == *" full "* ]]; then
        cmd_pytorch
    fi
    local m
    for m in $mods; do
        case "$m" in
            core)                              cmd_python ;;
            all)                               cmd_python "all" ;;
            full)                              cmd_python "full" ;;
            ai|control|vision|interface|sensors) cmd_python "$m" ;;
            *)                                 log_warning "Unknown module '$m' (skipped)" ;;
        esac
    done
}

# Guided one-shot install: used by menu option 1 and the non-interactive path.
# NOTE: GeographicLib is intentionally NOT installed here — it is a MAVROS-only
# dataset, set up by the 'mavros' driver (menu option 3 / make drone-mavros).
_quick_setup() {
    log_section "NECTAR SDK QUICK SETUP"
    log_info "Workspace: ${WORKSPACE_DIR}    ROS: ${ROS_DISTRO}"

    cmd_system
    cmd_git_lfs

    local modules
    modules="$(_select_modules)"
    log_info "Installing modules: ${modules}"
    _install_modules $modules

    cmd_rosdep_init
    cmd_ros2_deps
    cmd_build_pkg
    cmd_verify

    echo ""
    log_success "Setup complete."
    log_info "Configure your shell once with:  make ros2-env   (adds ROS sourcing + 'nectar-activate')"
}

# Drone driver sub-menu.
_menu_drone() {
    {
        echo ""
        echo "Drone driver / control type:"
        echo "  mavros     ArduPilot/PX4 over MAVROS (+ GeographicLib geoid)"
        echo "  px4        PX4 over MAVROS (px4.launch)"
        echo "  px4-dds    PX4 native uXRCE-DDS (px4_msgs + Micro XRCE-DDS Agent)"
        echo "  crazyflie  Crazyswarm2 (Crazyflie 2.x)"
        echo "  bebop      Parrot Bebop 2"
    } >&2
    local d
    read -r -p "Driver: " d || return 0
    [ -n "$d" ] && cmd_drone "$d"
}

# Interactive configuration menu. Each action returns to the menu; nothing is
# installed until the user picks something.
setup_menu() {
    while true; do
        echo ""
        echo -e "${PURPLE}=== Nectar SDK — Setup ===${NC}"
        echo -e "${BLUE}Workspace: ${WORKSPACE_DIR}    ROS: ${ROS_DISTRO}${NC}"
        echo ""
        echo "  1) Quick setup        system deps + choose modules + build + verify"
        echo "  2) Python modules     control / vision / ai / interface / sensors / all / full / core"
        echo "  3) Drone driver       mavros / px4 / px4-dds / crazyflie / bebop"
        echo "  4) System packages    apt deps (skips if already installed)"
        echo "  5) ROS 2 environment  configure ~/.bashrc (ROS sourcing + nectar-activate)"
        echo "  6) Build              build SDK packages"
        echo "  7) Verify             check installation"
        echo "  8) RealSense          Intel RealSense support"
        echo "  9) All commands       full command reference"
        echo "  0) Exit"
        echo ""
        local choice
        read -r -p "Select [0]: " choice || break
        case "${choice:-0}" in
            1) _quick_setup                       || log_error "Quick setup failed" ;;
            2) _install_modules "$(_select_modules)" || log_error "Module install failed" ;;
            3) _menu_drone                        || log_error "Driver setup failed" ;;
            4) cmd_system                         || log_error "System install failed" ;;
            5) cmd_ros2_env                       || log_error "ROS env config failed" ;;
            6) cmd_build_pkg                      || log_error "Build failed" ;;
            7) cmd_verify                         || true ;;
            8) cmd_realsense                      || log_error "RealSense install failed" ;;
            9) show_help ;;
            0|q|quit|exit) break ;;
            *) log_warning "Invalid option: ${choice}" ;;
        esac
    done
}

cmd_setup() {
    check_not_root
    check_distro

    # The menu configures an existing ROS 2 install; redirect fresh machines.
    if ! has_command ros2 && [ ! -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]; then
        log_error "ROS 2 not found at /opt/ros/${ROS_DISTRO}."
        log_info  "Fresh machine? Install everything (ROS 2 + SDK):  make full-install"
        log_info  "ROS under another distro?  ROS_DISTRO=<distro> make setup"
        return 1
    fi

    # No prompts available (CI / piped stdin) -> run the guided default unattended.
    if [[ "${NON_INTERACTIVE:-}" == "true" ]] || [ ! -t 0 ]; then
        _quick_setup
        return
    fi

    setup_menu
}

# Full installation (from zero)

cmd_full_install() {
    check_not_root
    check_distro

    cmd_update_system
    cmd_system
    cmd_git_lfs
    cmd_git_ssh
    cmd_ros2_install
    cmd_geographiclib
    cmd_clone_project
    cmd_python "all"
    cmd_rosdep_init
    cmd_ros2_env
    cmd_build
    cmd_verify
}

main() {
    local cmd="${1:-}"
    shift 2>/dev/null || true

    _activate_venv

    case "$cmd" in
        # No argument → setup menu (or `make full-install` for a fresh machine)
        "")                 cmd_setup ;;

        # Help
        help|--help|-h)     show_help ;;

        # System
        system)             cmd_system ;;
        update)             cmd_update_system ;;
        git-ssh)            cmd_git_ssh ;;
        git-lfs)            cmd_git_lfs ;;

        # ROS2
        ros2)               cmd_ros2_install ;;
        geographiclib)      cmd_geographiclib ;;
        ros2-env)           cmd_ros2_env ;;
        rosdep-init)        cmd_rosdep_init ;;

        # Drone drivers
        drone)              cmd_drone "$@" ;;

        # Python
        python)             cmd_python "$@" ;;
        pytorch)            cmd_pytorch "$@" ;;

        # Workspace
        clone)              cmd_clone_project ;;
        ros2-deps)          cmd_ros2_deps ;;
        build)              cmd_build ;;
        build-pkg)          cmd_build_pkg ;;
        clean)              cmd_clean ;;
        verify)             cmd_verify "$@" ;;
        verify-functional)  cmd_verify_functional "$@" ;;
        verify-hardware)    cmd_verify_hardware "$@" ;;
        verify-sitl)        cmd_verify_sitl "$@" ;;
        doctor)             cmd_doctor "$@" ;;
        test)               cmd_test ;;
        ci-local)           cmd_ci_local "$@" ;;

        # Hardware
        realsense)          cmd_realsense ;;
        realsense-verify)   cmd_realsense_verify ;;

        # Simulation — unified, parameterized (FIRMWARE/ENV/PROTOCOL via flags)
        sim-install)        cmd_sim_install "$@" ;;
        sim-start)          cmd_sim_start "$@" ;;
        sim-bridge)         cmd_sim_bridge "$@" ;;
        sim-stop)           cmd_sim_stop ;;

        # Real-hardware drivers/bridges (the real-world sim-bridge counterpart)
        driver)             cmd_driver "$@" ;;
        driver-stop)        cmd_driver_stop ;;

        # Docker
        docker-build)       cmd_docker_build "sdk" ;;
        docker-build-full)  cmd_docker_build "sdk-full" ;;
        docker-build-t265)  cmd_docker_build_t265 ;;
        docker-publish-jetson) cmd_docker_publish_jetson ;;
        docker-run)         cmd_docker_run ;;
        docker-exec)        cmd_docker_exec ;;
        # Setup
        setup)              cmd_setup ;;
        full-install)       cmd_full_install ;;

        *)
            log_error "Unknown command: $cmd"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
