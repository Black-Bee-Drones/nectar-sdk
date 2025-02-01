#!/bin/bash

# Configura permissões de exibição no X11
xhost +local:root

if [[ "$1" == "build" ]]; then
    echo "Construindo a imagem Docker..."
    docker build --network=host -t blackbee:ros2-humble -f docker/Dockerfile .
fi

echo "Iniciando o container..."
docker run -it \
    --name=ros2_black_bee \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$HOME/.Xauthority:/root/.Xauthority:rw" \
    --device-cgroup-rule='c 81:* rmw' \
    -v /dev/video0:/dev/video0 \
    -v /dev/bus/usb:/dev/bus/usb \
    --net=host \
    blackbee:ros2-humble \
    bash
