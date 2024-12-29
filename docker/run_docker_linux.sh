#!/bin/bash

# Configura permissões de exibição no X11
xhost +local:root
XAUTH=/tmp/.docker.xauth

docker build -t blackbee:ros2-humble -f docker/Dockerfile .

# Rodar o container
docker run -it \
    --name=ros2_black_bee \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --env="XAUTHORITY=$XAUTH" \
    --volume="$XAUTH:$XAUTH" \
    --device=/dev/video0:/dev/video0 \
    --net=host \
    blackbee:ros2-humble \
    bash
