# syntax=docker/dockerfile:1
ARG ROS_DISTRO=humble
FROM osrf/ros:${ROS_DISTRO}-desktop-full AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG ROS_DISTRO
ENV NON_INTERACTIVE=true
ENV ROS2_WORKSPACE=/home/ros2_ws
ENV ROS_DISTRO=${ROS_DISTRO}

COPY scripts/ /tmp/setup/scripts/

RUN /tmp/setup/scripts/setup.sh system
RUN /tmp/setup/scripts/setup.sh geographiclib
RUN apt-get remove -y python3-sympy 2>/dev/null || true
RUN python3 -m pip install --upgrade pip
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /home/ros2_ws/src
RUN /tmp/setup/scripts/setup.sh ros2-env

FROM base AS sdk

COPY . /home/ros2_ws/src/mirela-sdk

RUN --mount=type=cache,target=/root/.cache/pip \
    /home/ros2_ws/src/mirela-sdk/scripts/setup.sh python all
RUN /home/ros2_ws/src/mirela-sdk/scripts/setup.sh rosdep-init
RUN /home/ros2_ws/src/mirela-sdk/scripts/setup.sh ros2-deps
RUN /home/ros2_ws/src/mirela-sdk/scripts/setup.sh build

CMD ["/bin/bash"]

FROM sdk AS sdk-full

ARG TORCH_VARIANT=cpu
ENV TORCH_VARIANT=${TORCH_VARIANT}

RUN --mount=type=cache,target=/root/.cache/pip \
    /home/ros2_ws/src/mirela-sdk/scripts/setup.sh pytorch ${TORCH_VARIANT}
RUN --mount=type=cache,target=/root/.cache/pip \
    /home/ros2_ws/src/mirela-sdk/scripts/setup.sh python ai

CMD ["/bin/bash"]
