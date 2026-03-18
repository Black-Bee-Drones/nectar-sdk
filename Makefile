# Thin wrapper around scripts/setup.sh.

.PHONY: help setup system update ros2 geographiclib ros2-env rosdep-init \
        python python-control python-vision python-ai python-interface \
        install-all install-full pytorch \
        clone ros2-deps build build-pkg clean verify test \
        realsense realsense-verify \
        docker-build docker-build-full docker-run docker-exec \
        full-install \
        lint lint-fix format check \
        sim-install sim-install-gazebo sim-start sim-start-gazebo \
        sim-start-indoor sim-mavros sim-gazebo sim-outdoor sim-indoor sim-stop

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

# Python
python:             ; @$(SETUP) python
python-control:     ; @$(SETUP) python control
python-vision:      ; @$(SETUP) python vision
python-ai:          ; @$(SETUP) python ai
python-interface:   ; @$(SETUP) python interface
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
docker-run:         ; @$(SETUP) docker-run
docker-exec:        ; @$(SETUP) docker-exec

# Code quality
check:              ; @pre-commit run --all-files
lint:               ; @cd nectar && ruff check .
lint-fix:           ; @cd nectar && ruff check --fix .
format:             ; @cd nectar && ruff format .

# Simulation
sim-install:        ; @$(SETUP) sim-install
sim-install-gazebo: ; @$(SETUP) sim-install-gazebo
sim-start:          ; @$(SETUP) sim-start
sim-start-gazebo:   ; @$(SETUP) sim-start-gazebo
sim-start-indoor:   ; @$(SETUP) sim-start-indoor
sim-mavros:         ; @$(SETUP) sim-mavros
sim-gazebo:         ; @$(SETUP) sim-gazebo
sim-outdoor:        ; @$(SETUP) sim-outdoor
sim-indoor:         ; @$(SETUP) sim-indoor
sim-stop:           ; @$(SETUP) sim-stop

# Full setup from zero
full-install:       ; @$(SETUP) full-install
