# syntax=docker/dockerfile:1
ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO}-ros-base AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG ROS_DISTRO
ENV NON_INTERACTIVE=true
ENV ROS2_WORKSPACE=/home/ros2_ws
ENV ROS_DISTRO=${ROS_DISTRO}
ENV NECTAR_VENV=/home/ros2_ws/.venv
ENV PATH=/usr/local/bin:${NECTAR_VENV}/bin:$PATH

COPY scripts/ /tmp/setup/scripts/

RUN /tmp/setup/scripts/setup.sh system
RUN /tmp/setup/scripts/setup.sh geographiclib
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /home/ros2_ws/src
RUN /tmp/setup/scripts/setup.sh ros2-env

FROM base AS sdk

COPY . /home/ros2_ws/src/nectar-sdk
WORKDIR /home/ros2_ws/src/nectar-sdk

RUN --mount=type=cache,target=/root/.cache/uv make install-all
RUN make rosdep-init
RUN make ros2-deps
RUN make build

# Gazebo: simulation environment + ros_gz bridge + ArduPilot plugin
ARG INSTALL_GAZEBO=false
RUN if [ "$INSTALL_GAZEBO" = "true" ]; then \
    ./scripts/simulation/install_gazebo.sh; \
    fi

# RealSense: udev rules + hotplug for runtime device access
COPY docker/realsense/ /opt/realsense/
RUN chmod +x /opt/realsense/hotplug-realsense.sh 2>/dev/null || true
RUN mkdir -p /etc/udev/rules.d && \
    cp /opt/realsense/99-realsense-libusb-custom.rules /etc/udev/rules.d/99-realsense-libusb.rules 2>/dev/null || true

# RealSense: build librealsense from source + realsense-ros
ARG INSTALL_REALSENSE=false
ARG REALSENSE_CUDA=false
ARG LIBREALSENSE_VERSION
ARG REALSENSE_ROS_TAG
ENV REALSENSE_CUDA=${REALSENSE_CUDA}
ENV LIBREALSENSE_VERSION=${LIBREALSENSE_VERSION}
ENV REALSENSE_ROS_TAG=${REALSENSE_ROS_TAG}
RUN if [ "$INSTALL_REALSENSE" = "true" ]; then make realsense; fi
# After a from-source realsense build, re-pin numpy/scipy/sklearn inside the
# venv so the SDK's expected versions win regardless of what the build pulled in.
RUN if [ "$INSTALL_REALSENSE" = "true" ]; then \
    "${NECTAR_VENV}/bin/python" -m pip install --no-cache-dir \
        numpy==1.26.4 scipy==1.14.1 scikit-learn==1.7.2; \
    fi

# Control backends: space-separated list of `make drone-<x>` targets to install
# (e.g. "mavros crazyflie"). Empty by default (core install ships MAVLink/pymavlink
# only). Bebop is intentionally not a default (source build, heavy ARSDK).
ARG INSTALL_DRONE=""
RUN if [ -n "$INSTALL_DRONE" ]; then \
      if [ "$INSTALL_DRONE" = "all" ]; then make drone-all; \
      else for d in $INSTALL_DRONE; do make drone-$d; done; fi; \
    fi

# Simulation stack (opt-in): "ardupilot" | "px4" | "all" (see docker/README.md).
# ArduPilot's prereqs refuse root, so install_sitl.sh re-runs as AP_BUILD_USER;
# the built tree is symlinked to ~/ardupilot for the (root) runtime.
ARG INSTALL_SIM=""
ARG AP_BUILD_USER=nectar
ENV AP_BUILD_USER=${AP_BUILD_USER}
RUN if [ -n "$INSTALL_SIM" ]; then \
        make sim-install FIRMWARE="$INSTALL_SIM" && \
        if echo "$INSTALL_SIM" | grep -qwE 'ardupilot|all'; then \
            ln -sfn "/home/${AP_BUILD_USER}/ardupilot" /root/ardupilot; \
        fi; \
    fi

CMD ["/bin/bash"]

FROM sdk AS sdk-full

ARG TORCH_VARIANT=cpu
ARG INSTALL_REALSENSE=false
ENV TORCH_VARIANT=${TORCH_VARIANT}

RUN --mount=type=cache,target=/root/.cache/uv make pytorch
RUN --mount=type=cache,target=/root/.cache/uv make python-ai

RUN if [ "${INSTALL_REALSENSE:-false}" = "true" ]; then \
    "${NECTAR_VENV}/bin/python" -m pip install --no-cache-dir \
        numpy==1.26.4 scipy==1.14.1 scikit-learn==1.7.2; \
    fi

CMD ["/bin/bash"]
