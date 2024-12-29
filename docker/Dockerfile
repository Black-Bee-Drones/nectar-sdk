# Dockerfile para ambiente ROS2 Humble com MAVROS e SDK personalizado

# Base ROS2 Humble
FROM osrf/ros:humble-desktop-full

# Argumentos
ARG DEBIAN_FRONTEND=noninteractive

# Atualização e instalação de pacotes essenciais
RUN echo "⬆️  Atualizando e instalando pacotes essenciais..." && \
    apt-get update && apt-get install -y --no-install-recommends \
    nano \
    git \
    python3-pip \
    python3-colcon-common-extensions \
    tmux \
    ros-humble-mavros \
    ros-humble-mavros-extras \
    ros-humble-tf-transformations \
    ros-humble-ament-cmake \
    libboost-python-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Configuração do GeographicLib
RUN echo "🌍 Configurando GeographicLib para MAVROS..." && \
    wget https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh && \
    chmod +x install_geographiclib_datasets.sh && \
    ./install_geographiclib_datasets.sh && \
    rm install_geographiclib_datasets.sh

# Criar workspace ROS2
WORKDIR /home/ros2_ws/src

# Clonar repositórios públicos
RUN echo "📦 Clonando repositório vision_opencv para suporte a visão computacional..." && \
    git clone -b humble https://github.com/ros-perception/vision_opencv.git

# Copiar o repositório local para dentro do container
COPY . /home/ros2_ws/src/mirela-sdk
# Instalar dependências Python
RUN echo "🐍 Instalando dependências Python do mirela-sdk..." && \
    cd /home/ros2_ws/src/mirela-sdk && pip install -r requirements.txt

# Configurar ambiente ROS2
RUN echo "🔧 Configurando ambiente ROS2 no bashrc..." && \
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc \
    echo "source /home/ros2_ws/install/local_setup.bash" >> ~/.bashrc \
    echo "source /usr/share/colcon_cd/function/colcon_cd.sh" >> ~/.bashrc \
    echo "export ROS_DOMAIN_ID=14" >> ~/.bashrc \
    echo "export _colcon_cd_root=/opt/ros/humble/" >> ~/.bashrc

# Build do workspace
RUN echo "🔨 Construindo o workspace ROS2..." && \
    /bin/bash -c "source /opt/ros/humble/setup.bash && \
    cd /home/ros2_ws && \
    rosdep update && \
    rosdep install -i --from-path src --rosdistro humble -r -y && \
    colcon build --symlink-install && \
    source /home/ros2_ws/install/local_setup.bash"

RUN echo "🚀🐝 AVANTE! Ambiente ROS2 Humble com MAVROS e SDK pronto!"

CMD ["/bin/bash"]
