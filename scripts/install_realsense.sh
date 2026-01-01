#!/bin/bash

# =============================================================================
# MIRELA SDK - Script de Instalação RealSense D435i (Fixed Version)
# =============================================================================
# Este script instala o librealsense2 v2.55.1 e realsense-ros 4.55.1
# com suporte CUDA para Jetson Orin Nano.
# =============================================================================

set -e  

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' 

LIBREALSENSE_VERSION="v2.55.1"
REALSENSE_ROS_TAG="4.55.1"

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_section() {
    echo -e "\n${PURPLE}=== $1 ===${NC}\n"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Este script não deve ser executado como root!"
        log_info "Execute como usuário normal. O script pedirá sudo quando necessário."
        exit 1
    fi
}

check_existing_installations() {
    log_section "VERIFICANDO INSTALAÇÕES EXISTENTES"
    
    EXISTING_LIBREALSENSE=false
    EXISTING_ROS_LIBREALSENSE=false
    EXISTING_REALSENSE_ROS=false
   
    if [ -d "$HOME/librealsense" ]; then
        cd "$HOME/librealsense"
        CURRENT_VERSION=$(git describe --tags 2>/dev/null || echo "unknown")
        log_info "librealsense fonte encontrado: $CURRENT_VERSION"
        EXISTING_LIBREALSENSE=true
    fi
    
    if pkg-config --exists librealsense2 2>/dev/null; then
        PKG_VERSION=$(pkg-config --modversion librealsense2)
        log_info "librealsense2 (pkg-config): $PKG_VERSION"
    fi
    
    if dpkg -l | grep -q "ros-humble-librealsense2"; then
        ROS_VERSION=$(dpkg -l | grep "ros-humble-librealsense2" | awk '{print $3}')
        log_warning "ros-humble-librealsense2 (apt) encontrado: $ROS_VERSION"
        EXISTING_ROS_LIBREALSENSE=true
    fi
    
    if [ -d "$HOME/ros2_ws/src/realsense-ros" ]; then
        cd "$HOME/ros2_ws/src/realsense-ros"
        CURRENT_TAG=$(git describe --tags 2>/dev/null || git rev-parse --short HEAD || echo "unknown")
        log_info "realsense-ros encontrado (describe/commit): $CURRENT_TAG"
        EXISTING_REALSENSE_ROS=true
    fi
    
    if command -v rs-enumerate-devices &> /dev/null; then
        RS_VERSION=$(rs-enumerate-devices --version | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
        log_info "rs-enumerate-devices: $RS_VERSION"
    fi
}

remove_existing_installations() {
    log_section "REMOVENDO INSTALAÇÕES CONFLITANTES"

    if dpkg -l | grep -q "ros-humble-librealsense2"; then
        log_warning "Pacotes ros-humble-librealsense2 encontrados! Removendo automaticamente..."
        sudo apt remove -y ros-humble-librealsense2* || true
        sudo apt autoremove -y || true
        log_success "ros-humble-librealsense2 removido!"
    fi
    
    if [[ "$EXISTING_LIBREALSENSE" == "true" ]]; then
        read -p "Deseja reinstalar librealsense $LIBREALSENSE_VERSION? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            log_info "Removendo instalação anterior do librealsense..."
            cd "$HOME/librealsense"
            if [ -d "build" ]; then
                cd build
                sudo make uninstall 2>/dev/null || true
                cd ..
            fi
            cd "$HOME"
            rm -rf librealsense
            EXISTING_LIBREALSENSE=false
        fi
    fi
    
    if [[ "$EXISTING_REALSENSE_ROS" == "true" ]]; then
        read -p "Deseja reinstalar realsense-ros $REALSENSE_ROS_TAG? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            log_info "Removendo realsense-ros anterior..."
            rm -rf "$HOME/ros2_ws/src/realsense-ros"
            EXISTING_REALSENSE_ROS=false
        fi
    fi
}

check_cuda() {
    log_section "VERIFICANDO CUDA"
    
    if command -v nvcc &> /dev/null; then
        log_success "CUDA encontrado no PATH: $(nvcc --version | grep "release" | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')"
        USE_CUDA=true
        NVCC_PATH=$(which nvcc)
        log_info "NVCC path: $NVCC_PATH"

    elif [ -f /usr/local/cuda/bin/nvcc ]; then
        log_success "CUDA encontrado em /usr/local/cuda"
        USE_CUDA=true
        NVCC_PATH="/usr/local/cuda/bin/nvcc"
      
        export PATH=/usr/local/cuda/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
        CUDA_VERSION=$($NVCC_PATH --version | grep "release" | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')
        log_success "CUDA versão: $CUDA_VERSION"
        log_info "NVCC path: $NVCC_PATH"
  
    elif command -v nvidia-smi &> /dev/null; then
        log_info "nvidia-smi encontrado, procurando CUDA..."
        
        for cuda_dir in /usr/local/cuda-12* /usr/local/cuda-11*; do
            if [ -f "$cuda_dir/bin/nvcc" ]; then
                log_success "CUDA encontrado em $cuda_dir"
                USE_CUDA=true
                NVCC_PATH="$cuda_dir/bin/nvcc"
                export PATH=$cuda_dir/bin:$PATH
                export LD_LIBRARY_PATH=$cuda_dir/lib64:$LD_LIBRARY_PATH
                CUDA_VERSION=$($NVCC_PATH --version | grep "release" | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')
                log_success "CUDA versão: $CUDA_VERSION"
                log_info "NVCC path: $NVCC_PATH"
                break
            fi
        done
        
        if [ "$USE_CUDA" != "true" ]; then
            log_warning "nvidia-smi encontrado mas nvcc não localizado."
            log_warning "CUDA pode estar parcialmente instalado."
            USE_CUDA=false
        fi
    else
        log_warning "CUDA não encontrado. Instalando sem suporte CUDA."
        USE_CUDA=false
    fi
    
    if [ "$USE_CUDA" == "true" ]; then
        if $NVCC_PATH --version &> /dev/null; then
            log_success "CUDA está funcionando corretamente!"
        else
            log_error "CUDA encontrado mas nvcc não está funcionando."
            USE_CUDA=false
        fi
    fi
}

install_realsense_dependencies() {
    log_section "INSTALANDO DEPENDÊNCIAS REALSENSE"

    log_info "Adicionando repositório Universe..."
    sudo apt-add-repository universe -y
    sudo apt-get update

    log_info "Instalando dependências básicas..."
    sudo apt-get install -y \
        libssl-dev \
        libusb-1.0-0-dev \
        pkg-config \
        libgtk-3-dev \
        libglfw3-dev \
        libgl1-mesa-dev \
        libglu1-mesa-dev \
        qtcreator \
        python3 \
        python3-dev

    if [[ "$USE_CUDA" == "true" ]]; then
        log_info "Instalando bibliotecas OpenGL para Jetson..."
        sudo apt-get install -y \
            libgles2-mesa-dev \
            libegl1-mesa-dev
    fi

    log_success "Dependências RealSense instaladas!"
}

build_librealsense() {
    log_section "COMPILANDO LIBREALSENSE $LIBREALSENSE_VERSION"

    LIBREALSENSE_DIRECTORY=${HOME}/librealsense
    INSTALL_DIR=$PWD

    if [[ "$EXISTING_LIBREALSENSE" == "true" ]]; then
        cd "$LIBREALSENSE_DIRECTORY"
        CURRENT_VERSION=$(git describe --tags 2>/dev/null || echo "unknown")
        if [[ "$CURRENT_VERSION" == "$LIBREALSENSE_VERSION" ]]; then
            log_info "librealsense $LIBREALSENSE_VERSION já está instalado"
            return 0
        fi
    fi

    log_info "Versão do librealsense: $LIBREALSENSE_VERSION (FIXA)"

    if [ ! -d "$LIBREALSENSE_DIRECTORY" ]; then
        log_info "Clonando librealsense..."
        cd ${HOME}
        git clone https://github.com/IntelRealSense/librealsense.git
    fi

    cd $LIBREALSENSE_DIRECTORY

    if [ -d "build" ]; then
        log_info "Limpando build anterior..."
        rm -rf build
    fi

    git fetch --tags

    if ! git tag -l | grep -q "^${LIBREALSENSE_VERSION}$"; then
        log_error "Versão $LIBREALSENSE_VERSION não encontrada!"
        log_info "Versões disponíveis:"
        git tag -l | grep "^v2\." | tail -10
        exit 1
    fi

    log_info "Fazendo checkout da versão $LIBREALSENSE_VERSION..."
    git checkout $LIBREALSENSE_VERSION
    
    CURRENT_VERSION=$(git describe --tags)
    if [[ "$CURRENT_VERSION" != "$LIBREALSENSE_VERSION" ]]; then
        log_error "Falha ao fazer checkout da versão $LIBREALSENSE_VERSION"
        log_error "Versão atual: $CURRENT_VERSION"
        exit 1
    fi
    
    log_success "Checkout realizado: $CURRENT_VERSION"

    mkdir -p build
    cd build

    log_info "Configurando build do librealsense..."
    if [[ "$USE_CUDA" == "true" ]]; then
        log_info "Configurando com suporte CUDA..."
        export CUDACXX=$NVCC_PATH
        export PATH=${PATH}:/usr/local/cuda/bin
        export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/cuda/lib64

        cmake ../ -DBUILD_EXAMPLES=true \
                 -DFORCE_RSUSB_BACKEND=true \
                 -DBUILD_WITH_CUDA="$USE_CUDA" \
                 -DCMAKE_BUILD_TYPE=release \
                 -DBUILD_PYTHON_BINDINGS=bool:true \
                 -DPYTHON_EXECUTABLE=$(which python3)
    else
        log_info "Configurando sem suporte CUDA..."
        cmake ../ -DBUILD_EXAMPLES=true \
                 -DFORCE_RSUSB_BACKEND=true \
                 -DBUILD_WITH_CUDA=false \
                 -DCMAKE_BUILD_TYPE=release \
                 -DBUILD_PYTHON_BINDINGS=bool:true \
                 -DPYTHON_EXECUTABLE=$(which python3)
    fi

    log_info "Compilando librealsense..."
    NUM_PROCS=$(nproc)

    if ! time make -j$NUM_PROCS; then
        log_warning "Build falhou, tentando com 1 processo..."
        if ! time make; then
            log_error "Build falhou novamente!"
            exit 1
        fi
    fi

    log_info "Instalando librealsense..."
    sudo make install
    sudo ldconfig

    if grep -Fxq 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib' ~/.bashrc; then
        log_info "PYTHONPATH já configurado no .bashrc"
    else
        echo 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib' >> ~/.bashrc
        log_success "PYTHONPATH adicionado ao ~/.bashrc"
    fi

    cd $LIBREALSENSE_DIRECTORY

    log_info "Configurando regras udev..."
    sudo cp config/99-realsense-libusb.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules && sudo udevadm trigger

    log_success "librealsense $LIBREALSENSE_VERSION instalado com sucesso!"
}

install_realsense_ros() {
    log_section "INSTALANDO REALSENSE-ROS (tag: $REALSENSE_ROS_TAG)"

    WORKSPACE_DIR="$HOME/ros2_ws"

    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_error "Workspace ROS2 não encontrado em $WORKSPACE_DIR"
        log_info "Execute primeiro o install_env.sh"
        exit 1
    fi

    cd "$WORKSPACE_DIR/src"

    if [[ "$EXISTING_REALSENSE_ROS" == "true" ]]; then
        cd realsense-ros
        CURRENT_DESCRIBE=$(git describe --tags 2>/dev/null || echo "")
        if [[ "$CURRENT_DESCRIBE" == "$REALSENSE_ROS_TAG" ]]; then
            log_info "realsense-ros tag $REALSENSE_ROS_TAG já está instalado"
            cd ..
            return 0
        fi
        cd ..
    fi

    if [ ! -d "realsense-ros" ]; then
        log_info "Clonando realsense-ros..."
        git clone https://github.com/IntelRealSense/realsense-ros.git
        cd realsense-ros
        git fetch --tags origin
        if git tag -l | grep -q "^${REALSENSE_ROS_TAG}$"; then
            log_info "Fazendo checkout do tag ${REALSENSE_ROS_TAG}..."
            git checkout ${REALSENSE_ROS_TAG} || git checkout tags/${REALSENSE_ROS_TAG}
            log_success "realsense-ros ajustado para tag ${REALSENSE_ROS_TAG}"
        else
            log_error "Tag ${REALSENSE_ROS_TAG} não encontrada no repositório!"
            log_info "Tags disponíveis (últimas 20):"
            git tag -l | tail -20
            exit 1
        fi
    else
        log_info "Atualizando realsense-ros e ajustando para tag $REALSENSE_ROS_TAG..."
        cd realsense-ros

        git fetch --tags origin

        if git tag -l | grep -q "^${REALSENSE_ROS_TAG}$"; then
            git checkout ${REALSENSE_ROS_TAG} || git checkout tags/${REALSENSE_ROS_TAG}
            log_success "realsense-ros agora em tag ${REALSENSE_ROS_TAG}"
        else
            log_error "Tag ${REALSENSE_ROS_TAG} não encontrada!"
            log_info "Tags disponíveis (últimas 20):"
            git tag -l | tail -20
            exit 1
        fi
        cd ..
    fi

    log_success "realsense-ros (tag: $REALSENSE_ROS_TAG) preparado!"
}

install_vision_to_mavros() {
    log_section "INSTALANDO VISION_TO_MAVROS"

    WORKSPACE_DIR="$HOME/ros2_ws"

    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_error "Workspace ROS2 não encontrado em $WORKSPACE_DIR"
        log_info "Execute primeiro o install_env.sh"
        exit 1
    fi

    cd "$WORKSPACE_DIR/src"

    if [ ! -d "vision_to_mavros" ]; then
        log_info "Clonando vision_to_mavros..."
        git clone https://github.com/Black-Bee-Drones/vision_to_mavros.git
    else
        log_info "Atualizando vision_to_mavros..."
        cd vision_to_mavros
        git pull origin main
        cd ..
    fi

    log_success "vision_to_mavros preparado!"
}

rebuild_workspace() {
    log_section "RECONSTRUINDO WORKSPACE ROS2"

    WORKSPACE_DIR="$HOME/ros2_ws"

    cd "$WORKSPACE_DIR"

    source /opt/ros/humble/setup.bash

    log_info "Atualizando dependências..."
    rosdep update
    rosdep install -i --from-path src --rosdistro humble --skip-keys=librealsense2 -y

    log_info "Limpando builds anteriores..."
    rm -rf build/ install/ log/

    log_info "Construindo workspace..."
    colcon build --symlink-install

    log_success "Workspace reconstruído!"
}

verify_installation() {
    log_section "VERIFICANDO INSTALAÇÃO REALSENSE"

    LIBREALSENSE_FOUND=false

    if pkg-config --exists librealsense2 2>/dev/null; then
        PKG_VERSION=$(pkg-config --modversion librealsense2)
        log_success "librealsense2 encontrado via pkg-config: $PKG_VERSION"
        LIBREALSENSE_FOUND=true

        if [[ "$PKG_VERSION" == "2.55.1" ]]; then
            log_success "Versão correta (2.55.1) instalada!"
        else
            log_warning "Versão $PKG_VERSION encontrada, esperada 2.55.1"
        fi
    fi

    if command -v rs-enumerate-devices &> /dev/null; then
        RS_VERSION=$(rs-enumerate-devices --version | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
        log_success "rs-enumerate-devices versão: $RS_VERSION"
        LIBREALSENSE_FOUND=true

        if [[ "$RS_VERSION" == "2.55.1.0" ]]; then
            log_success "Versão correta das ferramentas (2.55.1.0) instalada!"
        else
            log_warning "Versão das ferramentas $RS_VERSION encontrada, esperada 2.55.1.0"
        fi
    fi

    if [ -f "/usr/local/lib/librealsense2.so" ] || [ -f "/usr/lib/x86_64-linux-gnu/librealsense2.so" ] || [ -f "/usr/lib/aarch64-linux-gnu/librealsense2.so" ]; then
        log_success "librealsense2 biblioteca encontrada no sistema"
        LIBREALSENSE_FOUND=true
    fi

    if [ "$LIBREALSENSE_FOUND" = false ]; then
        log_error "librealsense2 não encontrado!"
        return 1
    fi

    if dpkg -l | grep -q "ros-humble-librealsense2"; then
        log_warning "ATENÇÃO: ros-humble-librealsense2 (apt) ainda está instalado!"
        log_warning "Isso pode causar conflitos. Considere remover com:"
        log_warning "sudo apt remove ros-humble-librealsense2*"
    fi

    source /opt/ros/humble/setup.bash
    if [ -f "$HOME/ros2_ws/install/local_setup.bash" ]; then
        source "$HOME/ros2_ws/install/local_setup.bash"
    fi

    PKG_LIST=$(ros2 pkg list 2>/dev/null)
    if echo "$PKG_LIST" | grep -q "realsense2_camera"; then
        log_success "realsense2_camera encontrado no workspace!"
    else
        log_warning "realsense2_camera não encontrado no workspace"
    fi

    if echo "$PKG_LIST" | grep -q "vision_to_mavros"; then
        log_success "vision_to_mavros encontrado!"
    else
        log_warning "vision_to_mavros não encontrado no workspace"
    fi

    if [ -d "$HOME/librealsense" ]; then
        cd "$HOME/librealsense"
        CURRENT_VERSION=$(git describe --tags 2>/dev/null || echo "unknown")
        log_info "librealsense fonte: $CURRENT_VERSION"
    fi

    if [ -d "$HOME/ros2_ws/src/realsense-ros" ]; then
        cd "$HOME/ros2_ws/src/realsense-ros"
        CURRENT_TAG=$(git describe --tags 2>/dev/null || git rev-parse --short HEAD)
        log_info "realsense-ros describe/commit: $CURRENT_TAG"
    fi

    log_success "Verificação concluída!"
}

main() {
    log_info "Instalando librealsense $LIBREALSENSE_VERSION e realsense-ros tag $REALSENSE_ROS_TAG"

    check_root
    check_existing_installations
    check_cuda

    echo "Selecione as etapas a executar:"
    echo "1) Instalação completa com versões fixas (recomendado)"
    echo "2) Instalação personalizada"
    echo "3) Apenas verificar instalação"
    echo "4) Remover apenas instalações conflitantes"

    read -p "Opção [1]: " option
    option=${option:-1}

    case $option in
        1)
            remove_existing_installations
            install_realsense_dependencies
            build_librealsense
            install_realsense_ros
            install_vision_to_mavros
            rebuild_workspace
            verify_installation
            ;;
        2)
            echo "Selecione as etapas (separadas por espaço, ex: 1 3 5):"
            echo "1) Remover instalações conflitantes"
            echo "2) Instalar dependências RealSense"
            echo "3) Compilar librealsense $LIBREALSENSE_VERSION"
            echo "4) Instalar realsense-ros $REALSENSE_ROS_TAG"
            echo "5) Instalar vision_to_mavros"
            echo "6) Reconstruir workspace"
            echo "7) Verificar instalação"

            read -p "Etapas: " steps

            for step in $steps; do
                case $step in
                    1) remove_existing_installations ;;
                    2) install_realsense_dependencies ;;
                    3) build_librealsense ;;
                    4) install_realsense_ros ;;
                    5) install_vision_to_mavros ;;
                    6) rebuild_workspace ;;
                    7) verify_installation ;;
                    *) log_warning "Etapa $step inválida" ;;
                esac
            done
            ;;
        3)
            verify_installation
            ;;
        4)
            remove_existing_installations
            ;;
        *)
            log_error "Opção inválida!"
            exit 1
            ;;
    esac

    echo ""
    log_success "🐝 AVANTE!"
    log_info "librealsense: $LIBREALSENSE_VERSION"
    log_info "realsense-ros: $REALSENSE_ROS_TAG"
    
    if [ "$USE_CUDA" == "true" ] && ! command -v nvcc &> /dev/null; then
        log_warning "CUDA foi usado mas não está no PATH permanentemente."
        log_info "Para adicionar CUDA ao PATH permanentemente, execute:"
        echo "echo 'export PATH=/usr/local/cuda/bin:\$PATH' >> ~/.bashrc"
        echo "echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:\$LD_LIBRARY_PATH' >> ~/.bashrc"
    fi
    
    log_info "Para usar: source ~/.bashrc"
    log_info "Para testar IMU: ros2 launch realsense2_camera rs_launch.py enable_gyro:=true enable_accel:=true"
}

main "$@"
