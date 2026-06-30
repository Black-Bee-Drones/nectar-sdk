# Thin wrapper around scripts/setup.sh.

.PHONY: help setup system update ros2 geographiclib ros2-env rosdep-init \
        drone-mavros drone-px4 drone-px4-dds drone-crazyflie drone-bebop drone-all \
        python python-control python-vision python-ai python-interface python-sensors \
        python-all python-full python-dev install-all install-full pytorch \
        clone ros2-deps build build-pkg clean verify verify-functional verify-hardware verify-sitl doctor test ci-local \
        realsense realsense-verify \
        docker-build docker-build-full docker-build-t265 docker-run docker-exec \
        docker-publish-jetson \
        isaac-run isaac-stop vslam-viz \
        full-install \
        lint lint-fix format check \
        sim-install sim-start sim-bridge sim-stop \
        driver driver-mavros driver-px4 driver-px4-dds driver-bebop driver-crazyflie driver-stop

SETUP := ./scripts/setup.sh

help:
	@$(SETUP) help

# Quick start (install deps + build SDK packages)
setup:              ; @$(SETUP) setup

# System
system:             ; @$(SETUP) system
update:             ; @$(SETUP) update

# ROS2
ros2:               ; @$(SETUP) ros2
geographiclib:      ; @$(SETUP) geographiclib
ros2-env:           ; @$(SETUP) ros2-env
rosdep-init:        ; @$(SETUP) rosdep-init

# Drone drivers
drone-mavros:       ; @$(SETUP) drone mavros
drone-px4:          ; @$(SETUP) drone px4
drone-px4-dds:      ; @$(SETUP) drone px4-dds
drone-crazyflie:    ; @$(SETUP) drone crazyflie
drone-bebop:        ; @$(SETUP) drone bebop
drone-all:          ; @$(SETUP) drone all

# Python
python:             ; @$(SETUP) python
python-control:     ; @$(SETUP) python control
python-vision:      ; @$(SETUP) python vision
python-ai:          ; @$(SETUP) python ai
python-interface:   ; @$(SETUP) python interface
python-sensors:     ; @$(SETUP) python sensors
python-all:         ; @$(SETUP) python all
python-full:        ; @$(SETUP) python full
# Test/dev tooling (pytest, pytest-timeout) for the functional suite.
python-dev:         ; @$(SETUP) python dev
install-all:        ; @$(SETUP) python all     # alias of python-all (back-compat)
install-full:       ; @$(SETUP) python full    # alias of python-full (back-compat)
pytorch:            ; @$(SETUP) pytorch

# Workspace
clone:              ; @$(SETUP) clone
ros2-deps:          ; @$(SETUP) ros2-deps
build:              ; @$(SETUP) build
build-pkg:          ; @$(SETUP) build-pkg
clean:              ; @$(SETUP) clean
verify:             ; @$(SETUP) verify
# Functional regression tests (tier 2, pytest). MODULE= runs a subset (mapped to
# pytest markers), e.g. MODULE="vision control".
verify-functional:  ; @$(SETUP) verify-functional $(MODULE)
# Hardware-gated tests (opt-in; run on a rig with cameras/rangefinder attached).
verify-hardware:    ; @$(SETUP) verify-hardware
# SITL/integration flight tests in a headless sim (tier 3, pytest, opt-in; heavy).
# Default runs the full matrix; subset with FIRMWARE= (ardupilot|px4|crazyflie)
# and/or PROTOCOL= (mavros|mavlink|dds), e.g. `make verify-sitl FIRMWARE=px4 PROTOCOL=dds`.
# Only command-line FIRMWARE/PROTOCOL narrow it (the sim defaults below do not).
verify-sitl: ; @FW=""; [ "$(origin FIRMWARE)" = "command line" ] && FW="$(FIRMWARE)"; PR=""; [ "$(origin PROTOCOL)" = "command line" ] && PR="$(PROTOCOL)"; FIRMWARE="$$FW" PROTOCOL="$$PR" JUNIT_XML="$(JUNIT_XML)" $(SETUP) verify-sitl
# Read-only environment report (ROS env, installed modules, live devices, CUDA).
doctor:             ; @$(SETUP) doctor
test:               ; @$(SETUP) test
# Local cross-distro CI: build the SDK image per ROS distro from local source and
# run verify + verify-functional in each. Flags: DISTROS, FULL, REALSENSE, DRONES, KEEP.
#   make ci-local                       # humble jazzy kilted
#   make ci-local DISTROS=jazzy
#   make ci-local DISTROS="humble kilted" FULL=1
ci-local: ; @DISTROS="$(DISTROS)" TARGET="$(TARGET)" FULL="$(FULL)" REALSENSE="$(REALSENSE)" DRONES="$(DRONES)" KEEP="$(KEEP)" PRUNE_CACHE="$(PRUNE_CACHE)" $(SETUP) ci-local

# Hardware
realsense:          ; @$(SETUP) realsense
realsense-verify:   ; @$(SETUP) realsense-verify

# Docker
docker-build:       ; @$(SETUP) docker-build
docker-build-full:  ; @$(SETUP) docker-build-full
docker-build-t265:  ; @$(SETUP) docker-build-t265
docker-run:         ; @$(SETUP) docker-run
docker-exec:        ; @$(SETUP) docker-exec

# Publish the Jetson image to Docker Hub (run ON the Jetson, after `docker login`).
# Verifies (SDK + torch CUDA + RealSense) on this hardware, then pushes
# <NAMESPACE>/nectar-sdk:<variant>-<VERSION>, :<variant>-<JETPACK>, :<variant>.
#   make docker-publish-jetson JETSON_NAMESPACE=blackbee VERSION=v1.2.0
JETSON_NAMESPACE ?=
JETSON_TARGET    ?= sdk-full
JETSON_JETPACK   ?= jp6.2
docker-publish-jetson: ; @NAMESPACE="$(JETSON_NAMESPACE)" VERSION="$(VERSION)" TARGET="$(JETSON_TARGET)" JETPACK="$(JETSON_JETPACK)" $(SETUP) docker-publish-jetson

# Isaac ROS Visual SLAM (Jetson) - self-contained producer container
isaac-run:          ; @./docker/isaac_vslam/run_docker.sh
# Tear down Isaac containers
isaac-stop:         ; @docker rm -f isaac_ros_dev-aarch64-nectar-container isaac_ros_dev-aarch64-container 2>/dev/null; echo "Isaac containers removed"
# VSLAM RViz. PROFILE=light|full, WINDOW=rolling buffer seconds (light, 0=full history)
VSLAM_PROFILE ?= light
VSLAM_WINDOW  ?= 15.0
vslam-viz:          ; @ros2 launch nectar vslam_rviz.launch.py profile:=$(VSLAM_PROFILE) window_seconds:=$(VSLAM_WINDOW)

# Code quality
check:              ; @pre-commit run --all-files
lint:               ; @cd nectar && ruff check .
lint-fix:           ; @cd nectar && ruff check --fix .
format:             ; @cd nectar && ruff format .

# Simulation — unified, parameterized. Choose the firmware/environment/protocol
# with make variables; both firmwares follow the same two-terminal pattern.
#   FIRMWARE = ardupilot | px4         (sim-install also accepts: all)
#   ENV      = outdoor   | indoor
#   PROTOCOL = mavros    | mavlink     (mavlink is ArduPilot-only; px4 also: dds)
#   ARGS     = extra tokens forwarded to the underlying script/launch
#
# Example:
#   make sim-start  FIRMWARE=px4 ENV=outdoor          # Terminal 1
#   make sim-bridge FIRMWARE=px4 ENV=outdoor          # Terminal 2
FIRMWARE ?= ardupilot
ENV      ?= outdoor
PROTOCOL ?= mavros

sim-install: ; @$(SETUP) sim-install --firmware $(FIRMWARE) $(ARGS)
sim-start:   ; @$(SETUP) sim-start --firmware $(FIRMWARE) --env $(ENV) $(ARGS)
sim-bridge:  ; @$(SETUP) sim-bridge --firmware $(FIRMWARE) --env $(ENV) --protocol $(PROTOCOL) $(ARGS)
sim-stop:    ; @$(SETUP) sim-stop

# Real-hardware drivers/bridges — the real-world counterpart of sim-bridge.
# Starts the driver/bridge your mission script connects to (examples run with
# start_driver=False). Connection overrides via env: FCU_URL / DEV / BAUD / PORT / IP.
#   make driver DRONE=mavros ENV=outdoor FCU_URL=serial:///dev/ttyUSB0:921600
#   make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600     (or PORT=8888 for UDP)
DRONE ?=
driver:           ; @$(SETUP) driver $(DRONE) $(if $(DRONE),--env $(ENV)) $(ARGS)
driver-mavros:    ; @$(SETUP) driver mavros --env $(ENV) $(ARGS)
driver-px4:       ; @$(SETUP) driver px4 --env $(ENV) $(ARGS)
driver-px4-dds:   ; @$(SETUP) driver px4-dds $(ARGS)
driver-bebop:     ; @$(SETUP) driver bebop $(ARGS)
driver-crazyflie: ; @$(SETUP) driver crazyflie $(ARGS)
driver-stop:      ; @$(SETUP) driver-stop

# Full setup from zero
full-install:       ; @$(SETUP) full-install

# Documentation site (Zensical). Edit website/ (authored pages), the module
# READMEs, and docs/*.md; everything generated is assembled under build/.
#   make docs-install   create .venv-docs and install the doc toolchain
#   make docs-sync      assemble build/docs/ from website/ + READMEs + docs/*.md
#   make docs           sync, then compile the HTML into build/site/
#   make docs-serve     sync, then live preview at http://localhost:8000
.PHONY: docs-install docs-sync docs docs-serve
DOCS_VENV := .venv-docs
docs-install: ; @uv venv $(DOCS_VENV) && uv pip install --python $(DOCS_VENV)/bin/python -r scripts/docs/requirements.txt
docs-sync:    ; @$(DOCS_VENV)/bin/python scripts/docs/sync_readmes.py
docs:         ; @$(MAKE) docs-sync && $(DOCS_VENV)/bin/zensical build --clean
docs-serve:   ; @$(MAKE) docs-sync && $(DOCS_VENV)/bin/zensical serve
