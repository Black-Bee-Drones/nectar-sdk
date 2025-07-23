#!/bin/bash

# =============================================================================
# MIRELA SDK - Script de Instalação Completa
# =============================================================================
# Este script instala todas as dependências necessárias para executar o
# pacote mirela_sdk em um sistema Ubuntu/Debian sem Docker.
# 
# Baseado no Dockerfile oficial e otimizado para instalação local.
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

# Verificar distribuição Ubuntu/Debian
check_distro() {
    if ! command -v lsb_release &> /dev/null; then
        sudo apt update && sudo apt install -y lsb-release
    fi
    
    DISTRO=$(lsb_release -si)
    VERSION=$(lsb_release -sr)
    
    log_info "Detectado: $DISTRO $VERSION"
    
    if [[ "$DISTRO" != "Ubuntu" ]] && [[ "$DISTRO" != "Debian" ]]; then
        log_warning "Este script foi testado apenas em Ubuntu/Debian"
        read -p "Deseja continuar mesmo assim? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Atualizar sistema
update_system() {
    log_section "ATUALIZANDO SISTEMA"
    log_info "Atualizando lista de pacotes..."
    sudo apt update
    
    log_info "Atualizando pacotes instalados..."
    sudo apt upgrade -y
    
    log_success "Sistema atualizado!"
}

# Instalar pacotes essenciais
install_essential_packages() {
    log_section "INSTALANDO PACOTES ESSENCIAIS"
    
    local packages=(
        "nano"
        "git"
        "curl"
        "wget"
        "software-properties-common"
        "python3-pip"
        "python3-dev"
        "python3-venv"
        "build-essential"
        "cmake"
        "pkg-config"
        "libboost-python-dev"
        "tmux"
        "fswebcam"
        "v4l-utils"
        "lsb-release"
        "gnupg2"
    )
    
    log_info "Instalando pacotes essenciais..."
    sudo apt install -y --no-install-recommends "${packages[@]}"
    
    # Adicionar usuário ao grupo video para acesso à câmera
    sudo usermod -a -G video $USER
    
    log_success "Pacotes essenciais instalados!"
}

# Configurar Git e SSH
configure_git_ssh() {
    log_section "CONFIGURAÇÃO DO GIT E SSH"
    
    # Verificar se Git já está configurado
    if git config --global user.name &> /dev/null && git config --global user.email &> /dev/null; then
        log_info "Git já está configurado:"
        log_info "Nome: $(git config --global user.name)"
        log_info "Email: $(git config --global user.email)"
        
        read -p "Deseja reconfigurar? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return
        fi
    fi
    
    read -p "Digite seu nome completo para o Git: " git_name
    read -p "Digite seu e-mail do GitHub: " git_email
    
    git config --global user.name "$git_name"
    git config --global user.email "$git_email"
    
    # Configurar chave SSH se não existir
    if [ ! -f ~/.ssh/id_ed25519 ]; then
        log_info "Gerando chave SSH..."
        ssh-keygen -t ed25519 -C "$git_email" -f ~/.ssh/id_ed25519 -N ""
        eval "$(ssh-agent -s)"
        ssh-add ~/.ssh/id_ed25519
        
        echo ""
        log_warning "IMPORTANTE: Adicione a chave pública abaixo ao GitHub:"
        log_info "https://github.com/settings/keys"
        echo ""
        cat ~/.ssh/id_ed25519.pub
        echo ""
        read -p "Pressione Enter após adicionar a chave no GitHub..."
    else
        log_info "Chave SSH já existe."
    fi
    
    log_success "Git e SSH configurados!"
}

# Instalar ROS 2 Humble
install_ros2() {
    log_section "INSTALANDO ROS 2 HUMBLE"
    
    # Verificar se ROS 2 já está instalado
    if command -v ros2 &> /dev/null; then
        log_info "ROS 2 já está instalado."
        
        read -p "Deseja reinstalar? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return
        fi
    fi
    
    log_info "Adicionando repositório ROS 2..."
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | \
        sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    
    sudo apt update
    
    log_info "Instalando ROS 2 Humble Desktop..."
    sudo apt install -y ros-humble-desktop-full
    
    log_info "Instalando pacotes ROS 2 adicionais..."
    local ros_packages=(
        "ros-humble-mavros"
        "ros-humble-mavros-extras"
        "ros-humble-tf-transformations"
        "ros-humble-ament-cmake"
        "python3-colcon-common-extensions"
        "python3-rosdep"
    )
    
    sudo apt install -y "${ros_packages[@]}"
    
    log_success "ROS 2 Humble instalado!"
}

# Configurar GeographicLib para MAVROS
configure_geographiclib() {
    log_section "CONFIGURANDO GEOGRAPHICLIB PARA MAVROS"
    
    log_info "Baixando e executando script de configuração..."
    wget -q https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh
    chmod +x install_geographiclib_datasets.sh
    sudo ./install_geographiclib_datasets.sh
    rm install_geographiclib_datasets.sh
    
    log_success "GeographicLib configurado!"
}

# Clonar repositório mirela-sdk
clone_mirela_sdk() {
    log_section "CLONANDO REPOSITÓRIO MIRELA-SDK"
    
    # Definir diretório do workspace
    WORKSPACE_DIR="$HOME/ros2_ws"
    
    # Criar workspace se não existir
    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_info "Criando workspace ROS 2 em $WORKSPACE_DIR..."
        mkdir -p "$WORKSPACE_DIR/src"
    fi
    
    cd "$WORKSPACE_DIR/src"
    
    # Clonar mirela-sdk se não existir
    if [ ! -d "mirela-sdk" ]; then
        log_info "Clonando repositório mirela-sdk..."
        git clone git@github.com:Black-Bee-Drones/mirela-sdk.git
    else
        log_info "Repositório mirela-sdk já existe, atualizando..."
        cd mirela-sdk
        git pull origin main
        cd ..
    fi
    
    log_success "Repositório mirela-sdk clonado/atualizado!"
}

# Instalar dependências Python
install_python_dependencies() {
    log_section "INSTALANDO DEPENDÊNCIAS PYTHON"
    
    log_info "Atualizando pip..."
    python3 -m pip install --upgrade pip
    
    # Verificar se requirements.txt existe no mirela-sdk
    REQUIREMENTS_FILE="$HOME/ros2_ws/src/mirela-sdk/requirements.txt"
    if [ -f "$REQUIREMENTS_FILE" ]; then
        log_info "Instalando dependências do requirements.txt..."
        python3 -m pip install -r "$REQUIREMENTS_FILE"
    else
        log_info "Instalando dependências Python manualmente..."
        local python_packages=(
            "catkin-pkg==1.0.0"
            "opencv-python==4.10.0.84"
            "opencv-contrib-python==4.10.0.84"
            "cvzone==1.6.1"
            "pygeodesy==22.10.22"
            "shapely==2.0.6"
            "geopy==2.4.1"
            "scipy==1.13.1"
            "transforms3d==0.4.2"
            "numpy==1.26.4"
            "depthai==2.29.0.0"
        )
        
        for package in "${python_packages[@]}"; do
            log_info "Instalando $package..."
            python3 -m pip install "$package"
        done
    fi
    
    log_success "Dependências Python instaladas!"
}

# Configurar workspace ROS 2
setup_ros2_workspace() {
    log_section "CONFIGURANDO WORKSPACE ROS 2"
    
    # Definir diretório do workspace
    WORKSPACE_DIR="$HOME/ros2_ws"
    
    # Criar workspace se não existir
    if [ ! -d "$WORKSPACE_DIR" ]; then
        log_info "Criando workspace ROS 2 em $WORKSPACE_DIR..."
        mkdir -p "$WORKSPACE_DIR/src"
    else
        log_info "Workspace já existe em $WORKSPACE_DIR"
    fi
    
    cd "$WORKSPACE_DIR"
    
    # Inicializar rosdep se necessário
    if [ ! -f "/etc/ros/rosdep/sources.list.d/20-default.list" ]; then
        log_info "Inicializando rosdep..."
        sudo rosdep init
    fi
    
    log_info "Atualizando rosdep..."
    rosdep update
    
    # Clonar vision_opencv se não existir
    if [ ! -d "src/vision_opencv" ]; then
        log_info "Clonando vision_opencv..."
        cd src
        git clone -b humble https://github.com/ros-perception/vision_opencv.git
        cd ..
    fi
    
    log_success "Workspace configurado!"
}

# Configurar ambiente ROS 2
configure_ros2_environment() {
    log_section "CONFIGURANDO AMBIENTE ROS 2"
    
    # Backup do bashrc
    cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d_%H%M%S)
    
    # Remover configurações antigas do ROS se existirem
    sed -i '/# ROS 2 Configuration/,/# End ROS 2 Configuration/d' ~/.bashrc
    
    # Adicionar configurações ROS 2
    cat >> ~/.bashrc << 'EOF'

# ROS 2 Configuration
source /opt/ros/humble/setup.bash
if [ -f "$HOME/ros2_ws/install/local_setup.bash" ]; then
    source $HOME/ros2_ws/install/local_setup.bash
fi
source /usr/share/colcon_cd/function/colcon_cd.sh
export ROS_DOMAIN_ID=14
export _colcon_cd_root=/opt/ros/humble/
# End ROS 2 Configuration
EOF
    
    log_success "Ambiente ROS 2 configurado!"
}

# Build do workspace
build_workspace() {
    log_section "CONSTRUINDO WORKSPACE ROS 2"
    
    cd "$HOME/ros2_ws"
    
    # Source ROS 2
    source /opt/ros/humble/setup.bash
    
    log_info "Instalando dependências com rosdep..."
    rosdep install -i --from-path src --rosdistro humble -r -y
    
    log_info "Construindo workspace com colcon..."
    colcon build --symlink-install
    
    log_success "Workspace construído com sucesso!"
}

# Verificar instalação
verify_installation() {
    log_section "VERIFICANDO INSTALAÇÃO"
    
    # Source do ambiente
    source /opt/ros/humble/setup.bash
    if [ -f "$HOME/ros2_ws/install/local_setup.bash" ]; then
        source "$HOME/ros2_ws/install/local_setup.bash"
    fi
    
    log_info "Verificando ROS 2..."
    if command -v ros2 &> /dev/null; then
        # Usar uma forma alternativa para verificar a versão do ROS 2
        if [ -n "$ROS_DISTRO" ]; then
            log_success "ROS 2 instalado: ROS 2 $ROS_DISTRO"
        else
            # Fallback para verificar se o ROS 2 está funcionando
            if ros2 --help &> /dev/null; then
                log_success "ROS 2 instalado e funcionando"
            else
                log_warning "ROS 2 encontrado mas pode não estar configurado corretamente"
            fi
        fi
    else
        log_error "ROS 2 não encontrado!"
        return 1
    fi
    
    log_info "Verificando pacotes Python..."
    python3 -c "import cv2, numpy, scipy; print('OpenCV:', cv2.__version__, 'NumPy:', numpy.__version__, 'SciPy:', scipy.__version__)" 2>/dev/null || log_warning "Algumas dependências Python podem estar faltando"
    
    log_info "Verificando mirela_sdk..."
    # Usar uma abordagem mais robusta para verificar o pacote
    PKG_LIST=$(ros2 pkg list 2>/dev/null)
    if echo "$PKG_LIST" | grep -q "mirela_sdk"; then
        log_success "Pacote mirela_sdk encontrado!"
    else
        log_warning "Pacote mirela_sdk não encontrado no workspace"
    fi
    
    log_success "Verificação concluída!"
}

# Função principal
main() {
    log_section "MIRELA SDK - INSTALAÇÃO COMPLETA"
    log_info "Iniciando instalação do ambiente mirela_sdk..."
    
    check_root
    check_distro
    
    # Menu de opções
    echo "Selecione as etapas a executar:"
    echo "1) Instalação completa (recomendado)"
    echo "2) Instalação personalizada"
    echo "3) Apenas verificar instalação"
    
    read -p "Opção [1]: " option
    option=${option:-1}
    
    case $option in
        1)
            update_system
            install_essential_packages
            configure_git_ssh
            install_ros2
            configure_geographiclib
            clone_mirela_sdk
            install_python_dependencies
            setup_ros2_workspace
            configure_ros2_environment
            build_workspace
            verify_installation
            ;;
        2)
            echo "Selecione as etapas (separadas por espaço, ex: 1 3 5):"
            echo "1) Atualizar sistema"
            echo "2) Instalar pacotes essenciais"
            echo "3) Configurar Git/SSH"
            echo "4) Instalar ROS 2"
            echo "5) Configurar GeographicLib"
            echo "6) Clonar repositório mirela-sdk"
            echo "7) Instalar dependências Python"
            echo "8) Configurar workspace"
            echo "9) Configurar ambiente"
            echo "10) Build workspace"
            echo "11) Verificar instalação"
            
            read -p "Etapas: " steps
            
            for step in $steps; do
                case $step in
                    1) update_system ;;
                    2) install_essential_packages ;;
                    3) configure_git_ssh ;;
                    4) install_ros2 ;;
                    5) configure_geographiclib ;;
                    6) clone_mirela_sdk ;;
                    7) install_python_dependencies ;;
                    8) setup_ros2_workspace ;;
                    9) configure_ros2_environment ;;
                    10) build_workspace ;;
                    11) verify_installation ;;
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
    log_success "🚀🐝 AVANTE! Ambiente mirela_sdk configurado com sucesso!"
    log_info "Reinicie o terminal ou execute: source ~/.bashrc"
    log_info "Para testar: cd ~/ros2_ws && ros2 pkg list 2>/dev/null | grep mirela || echo 'Pacote não encontrado'"
}

# Executar função principal
main "$@" 
