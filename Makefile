# Thin wrapper around scripts/setup.sh.

.PHONY: help setup system update ros2 geographiclib ros2-env rosdep-init \
        drone-mavros drone-px4 drone-crazyflie drone-bebop drone-all \
        python python-control python-vision python-ai python-interface python-sensors \
        install-all install-full pytorch \
        clone ros2-deps build build-pkg clean verify test \
        realsense realsense-verify \
        docker-build docker-build-full docker-build-t265 docker-run docker-exec \
        isaac-run \
        full-install \
        lint lint-fix format check \
        sim-install sim-start sim-bridge sim-stop

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
install-all:        ; @$(SETUP) python all
install-full:       ; @$(SETUP) python full
pytorch:            ; @$(SETUP) pytorch

# Workspace
clone:              ; @$(SETUP) clone
ros2-deps:          ; @$(SETUP) ros2-deps
build:              ; @$(SETUP) build
build-pkg:          ; @$(SETUP) build-pkg
clean:              ; @$(SETUP) clean
verify:             ; @$(SETUP) verify
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

# Isaac ROS Visual SLAM (Jetson) - self-contained producer container
isaac-run:          ; @./docker/isaac_vslam/run_docker.sh

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

# Full setup from zero
full-install:       ; @$(SETUP) full-install
