# Thin wrapper around scripts/setup.sh.

.PHONY: help setup system update ros2 geographiclib ros2-env rosdep-init \
        drone-mavros drone-px4 drone-px4-dds drone-crazyflie drone-bebop drone-all \
        python python-control python-vision python-ai python-interface python-sensors \
        python-all python-full install-all install-full pytorch \
        clone ros2-deps build build-pkg clean verify verify-functional test \
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
# Functional harness (tier 2). MODULE= runs a subset, e.g. MODULE="vision control".
verify-functional:  ; @$(SETUP) verify-functional $(MODULE)
test:               ; @$(SETUP) test

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
