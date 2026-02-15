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
RUN rm -f /usr/lib/python*/EXTERNALLY-MANAGED
RUN python3 -m pip install --ignore-installed pip
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /home/ros2_ws/src
RUN /tmp/setup/scripts/setup.sh ros2-env

FROM base AS sdk

COPY . /home/ros2_ws/src/mirela-sdk

RUN --mount=type=cache,target=/root/.cache/pip \
    /home/ros2_ws/src/mirela-sdk/scripts/setup.sh python all
# Python 3.12+ (Jazzy): system numpy 1.26.4 == pip numpy → dual install causes
# RecursionError in sklearn/supervision. Remove the pip copy.
# Python 3.10 (Humble): system numpy 1.21.5 is too old, pip copy must stay.
RUN python3 -c "import sys; sys.exit(0 if sys.version_info>=(3,12) else 1)" \
    && rm -rf /usr/local/lib/python*/dist-packages/numpy /usr/local/lib/python*/dist-packages/numpy-* /usr/local/lib/python*/dist-packages/numpy.libs \
    || true
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
RUN python3 -c "import sys; sys.exit(0 if sys.version_info>=(3,12) else 1)" \
    && rm -rf /usr/local/lib/python*/dist-packages/numpy /usr/local/lib/python*/dist-packages/numpy-* /usr/local/lib/python*/dist-packages/numpy.libs \
    || true

CMD ["/bin/bash"]
