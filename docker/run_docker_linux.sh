#!/bin/bash

# Configura permissões de exibição no X11
xhost +local:root

# Configurações padrão
IMAGE_TYPE="base"  # ou "realsense"
CONTAINER_NAME="mirela_sdk_${IMAGE_TYPE}"

# Processar argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --realsense)
      IMAGE_TYPE="realsense"
      CONTAINER_NAME="mirela_sdk_realsense"
      shift
      ;;
    --base)
      IMAGE_TYPE="base"
      CONTAINER_NAME="mirela_sdk_base"
      shift
      ;;
    --build)
      BUILD_MODE="true"
      shift
      ;;
    --name)
      CONTAINER_NAME="$2"
      shift
      shift
      ;;
    --help)
      echo "Uso: $0 [opções]"
      echo "Opções:"
      echo "  --realsense    Usar imagem com suporte RealSense D435i"
      echo "  --base         Usar imagem base (padrão)"
      echo "  --build        Construir imagem antes de executar"
      echo "  --name NAME    Nome do container (padrão: mirela_sdk_<tipo>)"
      echo "  --help         Mostrar esta ajuda"
      exit 0
      ;;
    *)
      echo "Opção desconhecida: $1"
      echo "Use --help para ver as opções disponíveis"
      exit 1
      ;;
  esac
done

# Definir imagem baseada no tipo
if [[ "$IMAGE_TYPE" == "realsense" ]]; then
    IMAGE_NAME="mirela-sdk:realsense"
    DOCKERFILE="docker/Dockerfile.realsense"
else
    IMAGE_NAME="mirela-sdk:base"
    DOCKERFILE="docker/Dockerfile.base"
fi

# Construir imagem se solicitado
if [[ "$BUILD_MODE" == "true" ]]; then
    echo "🔨 Construindo imagem $IMAGE_NAME..."
    docker build --network=host -t "$IMAGE_NAME" -f "$DOCKERFILE" .
fi

# Verificar se imagem existe
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "❌ Imagem $IMAGE_NAME não encontrada!"
    echo "💡 Construa a imagem primeiro: $0 --$IMAGE_TYPE --build"
    exit 1
fi

# Remover container existente se houver
if docker ps -a --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "🧹 Removendo container existente..."
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
fi

echo "🚀 Iniciando container $CONTAINER_NAME com $IMAGE_NAME..."

# Executar container
docker run -it \
    --name="$CONTAINER_NAME" \
    --env="DISPLAY=$DISPLAY" \
    --env="QT_X11_NO_MITSHM=1" \
    --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume="$HOME/.Xauthority:/root/.Xauthority:rw" \
    --device-cgroup-rule='c 81:* rmw' \
    -v /dev/video0:/dev/video0 \
    -v /dev/video1:/dev/video1 \
    -v /dev/bus/usb:/dev/bus/usb \
    -v "$HOME/ros2_ws:/home/mirela/ros2_ws" \
    --net=host \
    --privileged \
    "$IMAGE_NAME" \
    bash
