#!/bin/bash
# =============================================================================
# Nectar SDK — Docker Dev Helper (Linux)
#
# Usage:
#   ./docker/run_docker_dev.sh build          Build the dev image
#   ./docker/run_docker_dev.sh run            Start dev container
#   ./docker/run_docker_dev.sh exec           Open another shell
#   ./docker/run_docker_dev.sh rebuild        Rebuild SDK packages
#   ./docker/run_docker_dev.sh sim-start      Start SITL (outdoor Gazebo)
#   ./docker/run_docker_dev.sh sim-start-indoor  Start SITL (indoor)
#   ./docker/run_docker_dev.sh sim-outdoor    Gazebo + MAVROS (outdoor)
#   ./docker/run_docker_dev.sh sim-indoor     Gazebo + MAVROS (indoor)
#   ./docker/run_docker_dev.sh sim-stop       Stop simulation
#   ./docker/run_docker_dev.sh clean          Remove build volumes
#   ./docker/run_docker_dev.sh help           Show this help
#
#   ROS_DISTRO          ROS 2 distro (default: jazzy)
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

ROS_DISTRO="${ROS_DISTRO:-jazzy}"
IMAGE_TAG="nectar-sdk:dev-${ROS_DISTRO}"
CONTAINER_NAME="nectar_dev_${ROS_DISTRO}"

VOL_BUILD="nectar-dev-build-${ROS_DISTRO}"
VOL_INSTALL="nectar-dev-install-${ROS_DISTRO}"
VOL_LOG="nectar-dev-log-${ROS_DISTRO}"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

log_info()    { echo -e "${CYAN}[dev]${NC} $*"; }
log_success() { echo -e "${GREEN}[dev]${NC} $*"; }
log_error()   { echo -e "${RED}[dev] ERROR:${NC} $*"; }

# ---- build ----
cmd_build() {
    local realsense_cuda="false"
    if command -v nvidia-smi &>/dev/null && nvidia-smi -L &>/dev/null; then
        realsense_cuda="true"
    fi

    log_info "Building dev image: ${IMAGE_TAG}"
    log_info "Includes: SDK deps + Gazebo Harmonic + ArduPilot SITL"
    log_info "RealSense CUDA build: ${realsense_cuda} (auto-detected via nvidia-smi)"
    log_info "First build may take 30-40 minutes."
    echo ""
    docker build --network=host \
        --build-arg ROS_DISTRO="${ROS_DISTRO}" \
        --build-arg REALSENSE_CUDA="${realsense_cuda}" \
        -t "${IMAGE_TAG}" \
        -f "${PROJECT_DIR}/docker/Dockerfile.dev" \
        "${PROJECT_DIR}"
    log_success "Image ${IMAGE_TAG} built."
}

# ---- run ----
cmd_run() {
    if ! docker image inspect "${IMAGE_TAG}" &>/dev/null; then
        log_error "Image ${IMAGE_TAG} not found. Run: $0 build"
        exit 1
    fi

    docker rm -f "${CONTAINER_NAME}" &>/dev/null || true
    xhost +local:root 2>/dev/null || true

    local xauth="${XAUTHORITY:-$HOME/.Xauthority}"
    local gpu_flag=""
    if command -v nvidia-smi &>/dev/null; then
        gpu_flag="--gpus all"
        log_info "NVIDIA GPU detected"
    fi

    local devices=()
    for dev in /dev/video*; do
        [ -e "$dev" ] && devices+=(--device="$dev:$dev")
    done
    [ -d /dev/bus/usb ] && devices+=(--device=/dev/bus/usb:/dev/bus/usb)

    local tty_flag="-i"
    [ -t 0 ] && tty_flag="-it"

    log_info "Starting container ${CONTAINER_NAME}"
    log_info "Source mount: ${PROJECT_DIR}"
    log_info "Gazebo Harmonic + ArduPilot SITL included"
    log_info ""
    log_info "Simulation workflow:"
    log_info "  $0 sim-start        # Terminal 1: start SITL"
    log_info "  $0 sim-outdoor      # Terminal 2: Gazebo + MAVROS"
    log_info "  $0 exec             # Terminal 3+: extra shells"
    echo ""

    # shellcheck disable=SC2086
    docker run ${tty_flag} --rm \
        --name="${CONTAINER_NAME}" \
        --env="DISPLAY=${DISPLAY}" \
        --env="QT_X11_NO_MITSHM=1" \
        --env="GZ_VERSION=harmonic" \
        --ipc=host \
        --net=host \
        --privileged \
        ${gpu_flag} \
        --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
        --volume="${xauth}:/root/.Xauthority:rw" \
        --volume="${PROJECT_DIR}:/home/ros2_ws/src/nectar-sdk:rw" \
        --volume="/home/lipe-pedras/burrices/obstacle-segmentation/rosbags/:/home/ros2_ws/rosbags:rw" \
        --volume="${VOL_BUILD}:/home/ros2_ws/build" \
        --volume="${VOL_INSTALL}:/home/ros2_ws/install" \
        --volume="${VOL_LOG}:/home/ros2_ws/log" \
        --device-cgroup-rule='c 81:* rmw' \
        "${devices[@]}" \
        "${IMAGE_TAG}" \
        bash
}

# ---- exec ----
cmd_exec() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
        log_error "Container ${CONTAINER_NAME} is not running. Run: $0 run"
        exit 1
    fi

    local tty_flag="-i"
    [ -t 0 ] && tty_flag="-it"

    log_info "Attaching to ${CONTAINER_NAME}"
    # shellcheck disable=SC2086
    docker exec ${tty_flag} \
        --env="DISPLAY=${DISPLAY}" \
        "${CONTAINER_NAME}" \
        /ros_entrypoint_dev.sh bash
}

# ---- rebuild ----
cmd_rebuild() {
    _require_running
    log_info "Rebuilding SDK workspace..."
    docker exec "${CONTAINER_NAME}" \
        /ros_entrypoint_dev.sh bash -c \
        "cd /home/ros2_ws && colcon build --symlink-install --packages-select nectar nectar_interfaces --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo && echo Done."
}

# ---- helper: require running container ----
_require_running() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
        log_error "Container ${CONTAINER_NAME} is not running. Run: $0 run"
        exit 1
    fi
}

# ---- helper: exec make target inside container ----
_make_in_container() {
    _require_running
    docker exec -it \
        --env="DISPLAY=${DISPLAY}" \
        --env="GZ_VERSION=harmonic" \
        "${CONTAINER_NAME}" \
        /ros_entrypoint_dev.sh bash -c "cd /home/ros2_ws/src/nectar-sdk && make $1"
}

# ---- simulation commands ----
cmd_sim_start()        { log_info "Starting SITL outdoor...";  _make_in_container sim-start-gazebo; }
cmd_sim_start_indoor() { log_info "Starting SITL indoor...";   _make_in_container sim-start-indoor; }
cmd_sim_outdoor()      { log_info "Launching Gazebo outdoor..."; _make_in_container sim-outdoor; }
cmd_sim_indoor()       { log_info "Launching Gazebo indoor...";  _make_in_container sim-indoor; }
cmd_sim_mavros()       { log_info "Launching MAVROS only...";    _make_in_container sim-mavros; }

cmd_sim_stop() {
    log_info "Stopping simulation..."
    docker exec "${CONTAINER_NAME}" bash -c \
        "cd /home/ros2_ws/src/nectar-sdk && make sim-stop" 2>/dev/null || true
    log_success "Simulation stopped."
}

# ---- clean ----
cmd_clean() {
    log_info "Removing build volumes..."
    docker rm -f "${CONTAINER_NAME}" &>/dev/null || true
    docker volume rm -f "${VOL_BUILD}" "${VOL_INSTALL}" "${VOL_LOG}" 2>/dev/null || true
    log_success "Volumes removed. Next run will trigger a fresh build."
}

# ---- help ----
cmd_help() {
    echo ""
    echo -e "${CYAN}Nectar SDK Docker Dev Helper${NC}"
    echo ""
    echo "Usage: $0 COMMAND"
    echo ""
    echo -e "${GREEN}Container:${NC}"
    echo "  build              Build the dev image"
    echo "  run                Start container with bind-mounted source"
    echo "  exec               Open a new shell in running container"
    echo "  rebuild            Rebuild SDK packages"
    echo "  clean              Remove build volumes"
    echo ""
    echo -e "${GREEN}Simulation:${NC}"
    echo "  sim-start          Start SITL in Gazebo mode"
    echo "  sim-start-indoor   Start SITL indoor mode"
    echo "  sim-outdoor        Launch Gazebo + MAVROS outdoor"
    echo "  sim-indoor         Launch Gazebo + MAVROS indoor"
    echo "  sim-mavros         Launch MAVROS only"
    echo "  sim-stop           Stop all simulation processes"
    echo ""
    echo -e "${GREEN}Quick start:${NC}"
    echo "  $0 build               # one-time build"
    echo "  $0 run                  # start container"
    echo "  $0 sim-start            # terminal 1"
    echo "  $0 sim-outdoor          # terminal 2"
    echo "  $0 exec                 # terminal 3+"
    echo ""
    echo "ROS_DISTRO=${ROS_DISTRO}"
    echo ""
}

# ---- main ----
case "${1:-help}" in
    build)             cmd_build ;;
    run)               cmd_run ;;
    exec)              cmd_exec ;;
    rebuild)           cmd_rebuild ;;
    sim-start)         cmd_sim_start ;;
    sim-start-indoor)  cmd_sim_start_indoor ;;
    sim-outdoor)       cmd_sim_outdoor ;;
    sim-indoor)        cmd_sim_indoor ;;
    sim-mavros)        cmd_sim_mavros ;;
    sim-stop)          cmd_sim_stop ;;
    clean)             cmd_clean ;;
    help|*)            cmd_help ;;
esac
