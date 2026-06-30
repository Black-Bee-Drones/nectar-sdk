#!/bin/bash
#
# Local cross-distro CI runner.
#
# Reproduces the main CI (.github/workflows/_build-verify.yml) on this machine:
# for each ROS 2 distro it builds the SDK image from the *local* source tree, then
# runs `setup.sh verify` (install/imports) and `setup.sh verify-functional` (the
# pytest functional suite) inside it, collecting a JUnit report per distro and
# printing one pass/fail summary at the end.
#
# amd64 only (host arch); arm64 is covered on the Jetson. Builds happen one distro
# at a time and each image is removed afterwards (unless KEEP=1) to bound disk use.
#
# Usage:
#   scripts/ci_local.sh [distro ...]
#   make ci-local
#   make ci-local DISTROS=jazzy
#   DISTROS="humble jazzy kilted" FULL=1 REALSENSE=1 DRONES="mavros crazyflie" KEEP=1 \
#       scripts/ci_local.sh
#
# Flags (environment):
#   DISTROS     space-separated distros            (default: humble jazzy kilted;
#                                                    positional args override it)
#   FULL=1      build the sdk-full stage (torch/AI; heavy ~10GB)  (default: sdk)
#   REALSENSE=1 build librealsense + run realsense-verify          (default: off)
#   DRONES      INSTALL_DRONE list, e.g. "mavros crazyflie"        (default: none)
#   KEEP=1      keep each image after testing                       (default: remove)
#   PRUNE_CACHE=1  `docker builder prune -f` between distros (frees space, slower)
#   MIN_FREE_GB  abort a build if the Docker disk has less free     (default: 8)
#   RESULTS_DIR  where JUnit reports are written     (default: <repo>/ci-local-results)

set -uo pipefail

_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$_HERE")"

# shellcheck source=/dev/null
source "${_HERE}/lib/common.sh" 2>/dev/null || true
if ! type -t log_section >/dev/null 2>&1; then
    log_info()    { echo "[INFO]  $1"; }
    log_success() { echo "[OK]    $1"; }
    log_warning() { echo "[WARN]  $1"; }
    log_error()   { echo "[ERROR] $1"; }
    log_section() { echo; echo "=== $1 ==="; echo; }
fi

# --- configuration ---------------------------------------------------------
DISTROS="${*:-${DISTROS:-humble jazzy kilted}}"
TARGET="${TARGET:-sdk}"
[ "${FULL:-0}" = "1" ] && TARGET="sdk-full"
[ "${REALSENSE:-0}" = "1" ] && RS_ARG="true" || RS_ARG="false"
DRONES="${DRONES:-}"
KEEP="${KEEP:-0}"
PRUNE_CACHE="${PRUNE_CACHE:-0}"
MIN_FREE_GB="${MIN_FREE_GB:-8}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT_DIR}/ci-local-results}"
DOCKERFILE="${PROJECT_DIR}/docker/Dockerfile"
IMAGE_PREFIX="nectar-sdk"
SETUP_IN_IMAGE="/home/ros2_ws/src/nectar-sdk/scripts/setup.sh"

SUMMARY=()
OVERALL_RC=0

_free_gb() {
    local root
    root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
    df -BG --output=avail "$root" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0
}

# Run a command inside the image with ROS + overlay sourced.
#   _in_image <image> <inner-cmd> [extra docker run args...]
# $ROS_DISTRO and the overlay are set by the image; the source lines stay
# single-quoted so they expand inside the container, not on the host. The
# inner command is expanded on the host (so ${d} etc. are already substituted).
_in_image() {
    local image="$1" inner="$2"
    shift 2
    docker run --rm "$@" "$image" bash -lc '
        source "/opt/ros/${ROS_DISTRO}/setup.bash"
        source /home/ros2_ws/install/local_setup.bash 2>/dev/null || true
        '"$inner"'
    '
}

run_distro() {
    local d="$1"
    local image="${IMAGE_PREFIX}:${d}-cilocal"
    local b="-" v="-" f="-" r="-"

    local free
    free="$(_free_gb)"
    if [ "${free:-0}" -lt "$MIN_FREE_GB" ]; then
        log_error "[$d] only ${free}G free on the Docker disk (< ${MIN_FREE_GB}G); skipping build."
        log_info  "Free space (docker system prune / remove images) or set MIN_FREE_GB lower."
        SUMMARY+=("$(printf '%-8s build=%-6s verify=%-6s functional=%-6s realsense=%-6s' \
            "$d" "SKIP(disk)" "-" "-" "-")")
        OVERALL_RC=1
        return
    fi

    log_section "[$d] BUILD  (target=$TARGET realsense=$RS_ARG drones='${DRONES:-none}')"
    if docker build -f "$DOCKERFILE" --target "$TARGET" \
            --build-arg ROS_DISTRO="$d" \
            --build-arg INSTALL_REALSENSE="$RS_ARG" \
            --build-arg INSTALL_DRONE="$DRONES" \
            -t "$image" "$PROJECT_DIR"; then
        b="PASS"; log_success "[$d] image built: $image"
    else
        b="FAIL"; OVERALL_RC=1
        log_error "[$d] build failed"
        SUMMARY+=("$(printf '%-8s build=%-6s verify=%-6s functional=%-6s realsense=%-6s' \
            "$d" "FAIL" "-" "-" "-")")
        return
    fi

    log_section "[$d] VERIFY (install / imports)"
    if _in_image "$image" "${SETUP_IN_IMAGE} verify"; then v="PASS"; else v="FAIL"; OVERALL_RC=1; fi

    log_section "[$d] VERIFY-FUNCTIONAL (pytest)"
    mkdir -p "$RESULTS_DIR"
    if _in_image "$image" \
            "JUNIT_XML=/tmp/results/functional-${d}-amd64.xml ${SETUP_IN_IMAGE} verify-functional" \
            -v "${RESULTS_DIR}:/tmp/results"; then
        f="PASS"
    else
        f="FAIL"; OVERALL_RC=1
    fi

    if [ "${REALSENSE:-0}" = "1" ]; then
        log_section "[$d] REALSENSE-VERIFY"
        if _in_image "$image" "${SETUP_IN_IMAGE} realsense-verify"; then r="PASS"; else r="FAIL"; OVERALL_RC=1; fi
    fi

    SUMMARY+=("$(printf '%-8s build=%-6s verify=%-6s functional=%-6s realsense=%-6s' \
        "$d" "$b" "$v" "$f" "$r")")

    if [ "$KEEP" != "1" ]; then
        docker image rm -f "$image" >/dev/null 2>&1 && log_info "[$d] removed image (KEEP=1 to retain)"
        [ "$PRUNE_CACHE" = "1" ] && docker builder prune -f >/dev/null 2>&1 && log_info "[$d] pruned build cache"
    fi
}

main() {
    if ! command -v docker >/dev/null 2>&1; then
        log_error "docker not found on PATH"; exit 1
    fi
    if [ ! -f "$DOCKERFILE" ]; then
        log_error "Dockerfile not found: $DOCKERFILE"; exit 1
    fi

    log_section "LOCAL CI: ${DISTROS}"
    log_info "target=${TARGET}  realsense=${RS_ARG}  drones='${DRONES:-none}'  keep=${KEEP}"
    log_info "results -> ${RESULTS_DIR}  (Docker disk free: $(_free_gb)G)"

    for d in $DISTROS; do
        run_distro "$d"
    done

    log_section "SUMMARY"
    for line in "${SUMMARY[@]}"; do echo "  $line"; done
    echo
    if [ "$OVERALL_RC" -eq 0 ]; then
        log_success "All distros passed. JUnit reports in ${RESULTS_DIR}"
    else
        log_error "One or more checks failed (see above)."
    fi
    return "$OVERALL_RC"
}

main
