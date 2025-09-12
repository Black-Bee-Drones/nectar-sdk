 #!/bin/bash
# =============================================================================
# MIRELA SDK - Script de Instalação RealSense D435i
# =============================================================================
# Este script instala o librealsense2 e dependências para Intel RealSense D435i
# com suporte CUDA para Jetson Orin Nano.
# Baseado nos scripts do projeto VSLAM-UAV.
# =============================================================================

set -e  # Sair em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Função para logging
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

# Verificar se está rodando como root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Este script não deve ser executado como root!"
        log_info "Execute como usuário normal. O script pedirá sudo quando necessário."
        exit 1
    fi
}

# Verificar se CUDA está disponível
check_cuda() {
    log_section "VERIFICANDO CUDA"
    
    # Primeiro, tentar encontrar nvcc no PATH
    if command -v nvcc &> /dev/null; then
        log_success "CUDA encontrado no PATH: $(nvcc --version | grep "release" | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')"
        USE_CUDA=true
        NVCC_PATH=$(which nvcc)
        log_info "NVCC path: $NVCC_PATH"
    # Se não estiver no PATH, procurar em locais comuns (Jetson)
    elif [ -f /usr/local/cuda/bin/nvcc ]; then
        log_success "CUDA encontrado em /usr/local/cuda"
        USE_CUDA=true
        NVCC_PATH="/usr/local/cuda/bin/nvcc"
        # Adicionar ao PATH temporariamente
        export PATH=/usr/local/cuda/bin:$PATH
        export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
        CUDA_VERSION=$($NVCC_PATH --version | grep "release" | sed -n 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/p')
        log_success "CUDA versão: $CUDA_VERSION"
        log_info "NVCC path: $NVCC_PATH"
    # Verificar se nvidia-smi está disponível (indicativo de CUDA)
    elif command -v nvidia-smi &> /dev/null; then
        log_info "nvidia-smi encontrado, procurando CUDA..."
        # Tentar encontrar CUDA em outros locais
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
    
    # Se CUDA foi encontrado, verificar se está funcionando
    if [ "$USE_CUDA" == "true" ]; then
        if $NVCC_PATH --version &> /dev/null; then
            log_success "CUDA está funcionando corretamente!"
        else
            log_error "CUDA encontrado mas nvcc não está funcionando."
            USE_CUDA=false
        fi
    fi
}

# Instalar dependências do RealSense
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

    # Instalar OpenGL para Jetson
    if [[ "$USE_CUDA" == "true" ]]; then
        log_info "Instalando bibliotecas OpenGL para Jetson..."
        sudo apt-get install -y \
            libgles2-mesa-dev \
            libegl1-mesa-dev
    fi

    log_success "Dependências RealSense instaladas!"
}

# Clonar e compilar librealsense
build_librealsense() {
    log_section "COMPILANDO LIBREALSENSE"

    LIBREALSENSE_DIRECTORY=${HOME}/librealsense
    INSTALL_DIR=$PWD

    # Verificar versão mais recente do librealsense
    log_info "Verificando versão mais recente do librealsense..."
    LIBREALSENSE_VERSION=$(wget -qO- https://api.github.com/repos/IntelRealSense/librealsense/releases/latest |
        grep -Po '"tag_name": "\K.*?(?=")')

    if [[ -z "$LIBREALSENSE_VERSION" ]]; then
        log_warning "Não foi possível obter versão mais recente, usando v2.55.1"
        LIBREALSENSE_VERSION="v2.55.1"
    fi

    log_info "Versão do librealsense: $LIBREALSENSE_VERSION"

    # Clonar se não existir
    if [ ! -d "$LIBREALSENSE_DIRECTORY" ]; then
        log_info "Clonando librealsense..."
        cd ${HOME}
        git clone https://github.com/IntelRealSense/librealsense.git
    fi

    cd $LIBREALSENSE_DIRECTORY

    # Verificar se a versão existe
    VERSION_TAG=$(git tag -l $LIBREALSENSE_VERSION)
    if [ ! "$VERSION_TAG" ]; then
        log_error "Versão $LIBREALSENSE_VERSION não encontrada!"
        log_info "Versões disponíveis:"
        git tag -l | tail -10
        exit 1
    fi

    # Checkout da versão
    git checkout $LIBREALSENSE_VERSION

    # Criar diretório de build
    mkdir -p build
    cd build

    # Configurar build com CUDA se disponível
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

    # Compilar
    log_info "Compilando librealsense..."
    NUM_PROCS=$(nproc)

    # Tentar compilar
    if ! time make -j$NUM_PROCS; then
        log_warning "Build falhou, tentando com 1 processo..."
        if ! time make; then
            log_error "Build falhou novamente!"
            exit 1
        fi
    fi

    # Instalar
    log_info "Instalando librealsense..."
    sudo make install

    # Configurar PYTHONPATH
    if grep -Fxq 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib' ~/.bashrc; then
        log_info "PYTHONPATH já configurado no .bashrc"
    else
        echo 'export PYTHONPATH=$PYTHONPATH:/usr/local/lib' >> ~/.bashrc
        log_success "PYTHONPATH adicionado ao ~/.bashrc"
    fi

    cd $LIBREALSENSE_DIRECTORY

    # Configurar udev rules
    log_info "Configurando regras udev..."
    sudo cp config/99-realsense-libusb.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules && sudo udevadm trigger

    log_success "librealsense instalado com sucesso!"
}

# Instalar realsense-ros
install_realsense_ros() {
    log_section "INSTALANDO REALSENSE-ROS"

    WORKSPACE_DIR="$HOME/ros2_ws"

    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_error "Workspace ROS2 não encontrado em $WORKSPACE_DIR"
        log_info "Execute primeiro o install_env.sh"
        exit 1
    fi

    cd "$WORKSPACE_DIR/src"

    # Clonar realsense-ros se não existir
    if [ ! -d "realsense-ros" ]; then
        log_info "Clonando realsense-ros..."
        # Usar branch compatível com librealsense2 instalado via apt
        git clone https://github.com/IntelRealSense/realsense-ros.git -b r/4.56.4
    else
        log_info "Atualizando realsense-ros..."
        cd realsense-ros
        # Verificar branch atual
        CURRENT_BRANCH=$(git branch --show-current)
        if [ "$CURRENT_BRANCH" != "r/4.56.4" ]; then
            log_warning "Mudando para branch compatível r/4.56.4..."
            git checkout r/4.56.4
        else
            git pull origin r/4.56.4
        fi
        cd ..
    fi

    log_success "realsense-ros preparado!"
}

# Instalar vision_to_mavros
install_vision_to_mavros() {
    log_section "INSTALANDO VISION_TO_MAVROS"

    WORKSPACE_DIR="$HOME/ros2_ws"

    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_error "Workspace ROS2 não encontrado em $WORKSPACE_DIR"
        log_info "Execute primeiro o install_env.sh"
        exit 1
    fi

    cd "$WORKSPACE_DIR/src"

    # Clonar vision_to_mavros se não existir
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

# Reconstruir workspace ROS2
rebuild_workspace() {
    log_section "RECONSTRUINDO WORKSPACE ROS2"

    WORKSPACE_DIR="$HOME/ros2_ws"

    cd "$WORKSPACE_DIR"

    # Source ROS2
    source /opt/ros/humble/setup.bash

    log_info "Atualizando dependências..."
    rosdep update
    rosdep install -i --from-path src --rosdistro humble -r -y

    log_info "Construindo workspace..."
    colcon build --symlink-install

    log_success "Workspace reconstruído!"
}

# Verificar instalação
verify_installation() {
    log_section "VERIFICANDO INSTALAÇÃO REALSENSE"

    # Verificar librealsense
    if pkg-config --exists librealsense2; then
        log_success "librealsense2 encontrado: $(pkg-config --modversion librealsense2)"
    else
        log_error "librealsense2 não encontrado!"
        return 1
    fi

    # Verificar pyrealsense2
    if python3 -c "import pyrealsense2 as rs; print('pyrealsense2 versão:', rs.__version__)" 2>/dev/null; then
        log_success "pyrealsense2 funcionando!"
    else
        log_warning "pyrealsense2 não encontrado ou não funcionando"
    fi

    # Verificar realsense-ros
    PKG_LIST=$(ros2 pkg list 2>/dev/null)
    if echo "$PKG_LIST" | grep -q "realsense2_camera"; then
        log_success "realsense2_camera encontrado!"
    else
        log_warning "realsense2_camera não encontrado no workspace"
    fi

    # Verificar vision_to_mavros
    if echo "$PKG_LIST" | grep -q "vision_to_mavros"; then
        log_success "vision_to_mavros encontrado!"
    else
        log_warning "vision_to_mavros não encontrado no workspace"
    fi

    log_success "Verificação concluída!"
}

# Função principal
main() {
    log_section "MIRELA SDK - INSTALAÇÃO REALSENSE D435i"
    log_info "Iniciando instalação do suporte RealSense..."

    check_root
    check_cuda

    # Menu de opções
    echo "Selecione as etapas a executar:"
    echo "1) Instalação completa (recomendado)"
    echo "2) Instalação personalizada"
    echo "3) Apenas verificar instalação"

    read -p "Opção [1]: " option
    option=${option:-1}

    case $option in
        1)
            install_realsense_dependencies
            build_librealsense
            install_realsense_ros
            install_vision_to_mavros
            rebuild_workspace
            verify_installation
            ;;
        2)
            echo "Selecione as etapas (separadas por espaço, ex: 1 3 5):"
            echo "1) Instalar dependências RealSense"
            echo "2) Compilar librealsense"
            echo "3) Instalar realsense-ros"
            echo "4) Instalar vision_to_mavros"
            echo "5) Reconstruir workspace"
            echo "6) Verificar instalação"

            read -p "Etapas: " steps

            for step in $steps; do
                case $step in
                    1) install_realsense_dependencies ;;
                    2) build_librealsense ;;
                    3) install_realsense_ros ;;
                    4) install_vision_to_mavros ;;
                    5) rebuild_workspace ;;
                    6) verify_installation ;;
                    *) log_warning "Etapa $step inválida" ;;
                esac
            done
            ;;
        3)
            verify_installation
            ;;
        *)
            log_error "Opção inválida!"
            exit 1
            ;;
    esac

    echo ""
    log_success "🚀🐝 AVANTE! Suporte RealSense D435i instalado com sucesso!"
    
    # Se CUDA foi detectado mas não está no PATH, sugerir adicionar
    if [ "$USE_CUDA" == "true" ] && ! command -v nvcc &> /dev/null; then
        log_warning "CUDA foi usado mas não está no PATH permanentemente."
        log_info "Para adicionar CUDA ao PATH permanentemente, execute:"
        echo "echo 'export PATH=/usr/local/cuda/bin:\$PATH' >> ~/.bashrc"
        echo "echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:\$LD_LIBRARY_PATH' >> ~/.bashrc"
    fi
    
    log_info "Para usar: source ~/.bashrc"
    log_info "Para testar: ros2 launch realsense2_camera rs_launch.py"
}

# Executar função principal
main "$@"