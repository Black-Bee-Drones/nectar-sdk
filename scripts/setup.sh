#!/bin/bash
# =============================================================================
# SDK Setup - Unified CLI for installation, build, and development.
#
# Usage:
#   ./setup.sh              Interactive menu
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

show_help() {
    echo ""
    echo -e "${PURPLE}  SDK Setup - Installation & Development CLI${NC}"
    echo -e "${PURPLE}  ===========================================${NC}"
    echo ""
    echo -e "${BLUE}Quick Start:${NC}"
    echo "  ./setup.sh setup              Install deps + build SDK packages (existing ROS2)"
    echo "  ./setup.sh full-install       Full installation from zero (ROS2 + deps + build)"
    echo "  ./setup.sh                    Interactive menu"
    echo ""
    echo -e "${BLUE}System:${NC}"
    echo "  ./setup.sh system             Install system packages (apt)"
    echo "  ./setup.sh update             Update system (apt upgrade)"
    echo "  ./setup.sh git-ssh            Configure git and SSH keys"
    echo "  ./setup.sh git-lfs            Install and initialize Git LFS"
    echo ""
    echo -e "${BLUE}ROS2:${NC}"
    echo "  ./setup.sh ros2               Install ROS2 ${ROS_DISTRO^} + MAVROS"
    echo "  ./setup.sh geographiclib      Install GeographicLib datasets"
    echo "  ./setup.sh ros2-env           Configure ROS2 in ~/.bashrc"
    echo "  ./setup.sh rosdep-init        Initialize rosdep"
    echo ""
    echo -e "${BLUE}Drone drivers:${NC}"
    echo "  ./setup.sh drone mavros       Install MAVROS (ArduPilot/PX4) + GeographicLib"
    echo "  ./setup.sh drone crazyflie    Install Crazyswarm2 (Crazyflie 2.x)"
    echo "  ./setup.sh drone bebop        Build Bebop driver (ros2_bebop_driver + ARSDK)"
    echo "  ./setup.sh drone all          Install all drone drivers"
    echo ""
    echo -e "${BLUE}Python Dependencies:${NC}"
    echo "  ./setup.sh python             Install core dependencies"
    echo "  ./setup.sh python control     Install core + control module"
    echo "  ./setup.sh python vision      Install core + vision module"
    echo "  ./setup.sh python ai          Install core + AI module"
    echo "  ./setup.sh python interface   Install core + GUI module"
    echo "  ./setup.sh python all         Install all modules (no AI)"
    echo "  ./setup.sh python full        Install everything (all + AI)"
    echo "  ./setup.sh pytorch            Install PyTorch (auto-detect CUDA)"
    echo "  ./setup.sh pytorch cpu        Install PyTorch CPU"
    echo "  ./setup.sh pytorch cu124      Install PyTorch CUDA 12.4"
    echo ""
    echo -e "${BLUE}Workspace:${NC}"
    echo "  ./setup.sh clone              Clone project into workspace"
    echo "  ./setup.sh ros2-deps          Install ROS2 package deps (rosdep)"
    echo "  ./setup.sh build              Build entire workspace"
    echo "  ./setup.sh build-pkg          Build SDK packages only"
    echo "  ./setup.sh clean              Clean build artifacts"
    echo "  ./setup.sh verify             Verify installation"
    echo "  ./setup.sh test               Run tests"
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
    )
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

# Setup (existing ROS2 workspace — install deps + build SDK packages)

cmd_setup() {
    cmd_system
    cmd_git_lfs
    cmd_geographiclib
    cmd_python "all"
    cmd_rosdep_init
    cmd_ros2_deps
    cmd_build_pkg
    cmd_verify
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

# Menu

interactive_menu() {
    check_not_root
    check_distro

    echo ""
    echo -e "${PURPLE}  SDK Setup${NC}"
    echo ""
    echo "Select option:"
    echo "  1) Full installation (recommended for new machines)"
    echo "  2) Custom installation (select individual steps)"
    echo "  3) Install Python dependencies only"
    echo "  4) Build workspace"
    echo "  5) Install RealSense support"
    echo "  6) Verify installation"
    echo "  7) Show all commands"
    echo ""
    read -p "Option [1]: " option
    option=${option:-1}

    case $option in
        1)
            cmd_full_install
            ;;
        2)
            echo ""
            echo "Select steps (space-separated, e.g., 1 3 5):"
            echo "  1) Update system        2) System packages    3) Git LFS"
            echo "  4) Git/SSH               5) ROS2               6) GeographicLib"
            echo "  7) Clone repo            8) Python deps (all)  9) rosdep init"
            echo "  10) ROS2 env             11) Build workspace   12) Verify"
            echo ""
            read -p "Steps: " steps
            for step in $steps; do
                case $step in
                    1)  cmd_update_system ;;
                    2)  cmd_system ;;
                    3)  cmd_git_lfs ;;
                    4)  cmd_git_ssh ;;
                    5)  cmd_ros2_install ;;
                    6)  cmd_geographiclib ;;
                    7)  cmd_clone_project ;;
                    8)  cmd_python "all" ;;
                    9)  cmd_rosdep_init ;;
                    10) cmd_ros2_env ;;
                    11) cmd_build ;;
                    12) cmd_verify ;;
                    *)  log_warning "Invalid step: $step" ;;
                esac
            done
            ;;
        3)
            echo ""
            echo "Select Python extras:"
            echo "  1) core only    2) control    3) vision    4) ai"
            echo "  5) interface    6) all        7) full (all + AI)"
            echo ""
            read -p "Option [6]: " py_opt
            py_opt=${py_opt:-6}
            case $py_opt in
                1) cmd_python ;;
                2) cmd_python "control" ;;
                3) cmd_python "vision" ;;
                4) cmd_python "ai" ;;
                5) cmd_python "interface" ;;
                6) cmd_python "all" ;;
                7) cmd_python "full" ;;
                *) log_error "Invalid option" ;;
            esac
            ;;
        4) cmd_build ;;
        5) cmd_realsense ;;
        6) cmd_verify ;;
        7) show_help ;;
        *) log_error "Invalid option"; exit 1 ;;
    esac

    echo ""
    log_success "Done! Run: source ~/.bashrc"
}

main() {
    local cmd="${1:-}"
    shift 2>/dev/null || true

    case "$cmd" in
        # No argument → interactive menu
        "")                 interactive_menu ;;

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
        test)               cmd_test ;;

        # Hardware
        realsense)          cmd_realsense ;;
        realsense-verify)   cmd_realsense_verify ;;

        # Simulation — unified, parameterized (FIRMWARE/ENV/PROTOCOL via flags)
        sim-install)        cmd_sim_install "$@" ;;
        sim-start)          cmd_sim_start "$@" ;;
        sim-bridge)         cmd_sim_bridge "$@" ;;
        sim-stop)           cmd_sim_stop ;;

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
