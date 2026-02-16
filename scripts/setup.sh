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
source "$SCRIPT_DIR/lib/git.sh"
source "$SCRIPT_DIR/lib/realsense.sh"

show_help() {
    echo ""
    echo -e "${PURPLE}  SDK Setup - Installation & Development CLI${NC}"
    echo -e "${PURPLE}  ===========================================${NC}"
    echo ""
    echo -e "${BLUE}Full Setup (from zero):${NC}"
    echo "  ./setup.sh full-install       Full installation (ROS2 + deps + build)"
    echo "  ./setup.sh                    Interactive menu"
    echo ""
    echo -e "${BLUE}System:${NC}"
    echo "  ./setup.sh system             Install system packages (apt)"
    echo "  ./setup.sh update             Update system (apt upgrade)"
    echo "  ./setup.sh git-ssh            Configure git and SSH keys"
    echo ""
    echo -e "${BLUE}ROS2:${NC}"
    echo "  ./setup.sh ros2               Install ROS2 ${ROS_DISTRO^} + MAVROS"
    echo "  ./setup.sh geographiclib      Install GeographicLib datasets"
    echo "  ./setup.sh ros2-env           Configure ROS2 in ~/.bashrc"
    echo "  ./setup.sh rosdep-init        Initialize rosdep"
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
    echo "  ./setup.sh docker-run         Run container (selects image, GPU auto)"
    echo "  ./setup.sh docker-exec        Open new shell in running container"
    echo ""
    echo -e "${BLUE}Docker env vars:${NC}"
    echo "  ROS_DISTRO=jazzy              Build for different ROS distro"
    echo "  TORCH_VARIANT=cu124           Build full with CUDA PyTorch"
    echo "  TORCH_VARIANT=auto            Auto-detect CUDA from nvidia-smi"
    echo "  TORCH_VERSION=2.7.1           Pin specific torch version"
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
    local variant="${TORCH_VARIANT}"

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

    log_info "Building $tag (target=$target, distro=$ROS_DISTRO, torch=$variant)..."
    docker build --network=host \
        --build-arg ROS_DISTRO="${ROS_DISTRO}" \
        --build-arg TORCH_VARIANT="${variant}" \
        --build-arg INSTALL_REALSENSE="${INSTALL_REALSENSE:-false}" \
        --build-arg REALSENSE_CUDA="${REALSENSE_CUDA:-false}" \
        --target "$target" \
        -t "$tag" \
        -f "${PROJECT_DIR}/docker/Dockerfile" "$PROJECT_DIR"
    log_success "Docker image $tag built"
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
    [ -d /dev/bus/usb ] && devices+=(--device=/dev/bus/usb:/dev/bus/usb)

    if [ ${#devices[@]} -eq 0 ]; then
        log_warning "No video devices found. Webcam nodes won't work."
    fi

    local gpu_flag=""
    if command -v nvidia-smi &>/dev/null; then
        gpu_flag="--gpus all"
        log_info "NVIDIA GPU detected"
    fi

    local tty_flag="-i"
    [ -t 0 ] && tty_flag="-it"

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
        --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
        --volume="$xauth:/root/.Xauthority:rw" \
        --device-cgroup-rule='c 81:* rmw' \
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

# Full installation (from zero)

cmd_full_install() {
    check_not_root
    check_distro

    cmd_update_system
    cmd_system
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
            echo "  1) Update system        2) System packages    3) Git/SSH"
            echo "  4) ROS2                 5) GeographicLib      6) Clone repo"
            echo "  7) Python deps (all)    8) rosdep init        9) ROS2 env"
            echo "  10) Build workspace     11) Verify"
            echo ""
            read -p "Steps: " steps
            for step in $steps; do
                case $step in
                    1)  cmd_update_system ;;
                    2)  cmd_system ;;
                    3)  cmd_git_ssh ;;
                    4)  cmd_ros2_install ;;
                    5)  cmd_geographiclib ;;
                    6)  cmd_clone_project ;;
                    7)  cmd_python "all" ;;
                    8)  cmd_rosdep_init ;;
                    9)  cmd_ros2_env ;;
                    10) cmd_build ;;
                    11) cmd_verify ;;
                    *)  log_warning "Invalid step: $step" ;;
                esac
            done
            ;;
        3)
            echo ""
            echo "Select Python extras:"
            echo "  1) core only    2) control    3) vision    4) ai"
            echo "  5) interface    6) all        7) full (all + cameras)"
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

        # ROS2
        ros2)               cmd_ros2_install ;;
        geographiclib)      cmd_geographiclib ;;
        ros2-env)           cmd_ros2_env ;;
        rosdep-init)        cmd_rosdep_init ;;

        # Python
        python)             cmd_python "$@" ;;
        pytorch)            cmd_pytorch "$@" ;;

        # Workspace
        clone)              cmd_clone_project ;;
        ros2-deps)          cmd_ros2_deps ;;
        build)              cmd_build ;;
        build-pkg)          cmd_build_pkg ;;
        clean)              cmd_clean ;;
        verify)             cmd_verify ;;
        test)               cmd_test ;;

        # Hardware
        realsense)          cmd_realsense ;;
        realsense-verify)   cmd_realsense_verify ;;

        # Docker
        docker-build)       cmd_docker_build "sdk" ;;
        docker-build-full)  cmd_docker_build "sdk-full" ;;
        docker-run)         cmd_docker_run ;;
        docker-exec)        cmd_docker_exec ;;
        # Full
        full-install)       cmd_full_install ;;

        *)
            log_error "Unknown command: $cmd"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
