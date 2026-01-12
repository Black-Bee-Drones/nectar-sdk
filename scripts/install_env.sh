#!/bin/bash
# MIRELA SDK - Installation Script
# Installs all dependencies for mirela_sdk on Ubuntu/Debian

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_section() { echo -e "\n${PURPLE}=== $1 ===${NC}\n"; }

WORKSPACE_DIR="$HOME/ros2_ws"

check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "Do not run as root. Script will use sudo when needed."
        exit 1
    fi
}

check_distro() {
    command -v lsb_release &> /dev/null || sudo apt install -y lsb-release
    DISTRO=$(lsb_release -si)
    VERSION=$(lsb_release -sr)
    log_info "Detected: $DISTRO $VERSION"
    
    if [[ "$DISTRO" != "Ubuntu" ]] && [[ "$DISTRO" != "Debian" ]]; then
        log_warning "Only tested on Ubuntu/Debian"
        read -p "Continue anyway? (y/N): " -n 1 -r && echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
    fi
}

update_system() {
    log_section "UPDATING SYSTEM"
    sudo apt update && sudo apt upgrade -y
    log_success "System updated"
}

install_essential_packages() {
    log_section "INSTALLING ESSENTIAL PACKAGES"
    sudo apt install -y --no-install-recommends \
        git curl wget software-properties-common \
        python3-pip python3-dev build-essential cmake pkg-config \
        libboost-python-dev tmux fswebcam v4l-utils lsb-release gnupg2
    sudo usermod -a -G video $USER
    log_success "Essential packages installed"
}

configure_git_ssh() {
    log_section "CONFIGURING GIT & SSH"
    
    if git config --global user.name &> /dev/null; then
        log_info "Git configured: $(git config --global user.name) <$(git config --global user.email)>"
        read -p "Reconfigure? (y/N): " -n 1 -r && echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && return
    fi
    
    read -p "Git name: " git_name
    read -p "Git email: " git_email
    git config --global user.name "$git_name"
    git config --global user.email "$git_email"
    
    if [ ! -f ~/.ssh/id_ed25519 ]; then
        log_info "Generating SSH key..."
        ssh-keygen -t ed25519 -C "$git_email" -f ~/.ssh/id_ed25519 -N ""
        eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519
        echo ""
        log_warning "Add this key to GitHub: https://github.com/settings/keys"
        cat ~/.ssh/id_ed25519.pub
        read -p "Press Enter after adding key to GitHub..."
    fi
    log_success "Git & SSH configured"
}

install_ros2() {
    log_section "INSTALLING ROS 2 HUMBLE"
    
    if command -v ros2 &> /dev/null; then
        log_info "ROS 2 already installed"
        read -p "Reinstall? (y/N): " -n 1 -r && echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && return
    fi
    
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | \
        sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    
    sudo apt update
    sudo apt install -y ros-humble-desktop-full \
        ros-humble-mavros ros-humble-mavros-extras ros-humble-tf-transformations \
        ros-humble-vision-opencv ros-humble-cv-bridge ros-humble-image-geometry \
        python3-colcon-common-extensions python3-rosdep
    
    log_success "ROS 2 Humble installed"
}

configure_geographiclib() {
    log_section "CONFIGURING GEOGRAPHICLIB"
    wget -q https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh
    chmod +x install_geographiclib_datasets.sh
    sudo ./install_geographiclib_datasets.sh
    rm install_geographiclib_datasets.sh
    log_success "GeographicLib configured"
}

clone_mirela_sdk() {
    log_section "CLONING MIRELA-SDK"
    mkdir -p "$WORKSPACE_DIR/src"
    cd "$WORKSPACE_DIR/src"
    
    if [ ! -d "mirela-sdk" ]; then
        git clone git@github.com:Black-Bee-Drones/mirela-sdk.git
    else
        log_info "Updating existing repository..."
        cd mirela-sdk && git pull origin main && cd ..
    fi
    log_success "mirela-sdk ready"
}

install_python_dependencies() {
    log_section "INSTALLING PYTHON DEPENDENCIES"
    python3 -m pip install --upgrade pip
    
    REQUIREMENTS_FILE="$WORKSPACE_DIR/src/mirela-sdk/requirements.txt"
    if [ -f "$REQUIREMENTS_FILE" ]; then
        python3 -m pip install -r "$REQUIREMENTS_FILE"
    else
        log_warning "requirements.txt not found, install manually"
    fi
    
    # AI dependencies (optional)
    AI_REQUIREMENTS="$WORKSPACE_DIR/src/mirela-sdk/requirements-ai.txt"
    if [ -f "$AI_REQUIREMENTS" ]; then
        read -p "Install AI/Detection dependencies? (y/N): " -n 1 -r && echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if command -v nvidia-smi &> /dev/null; then
                log_info "Installing PyTorch with CUDA..."
                python3 -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu124
            else
                log_info "Installing PyTorch CPU..."
                python3 -m pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu
            fi
            python3 -m pip install -r "$AI_REQUIREMENTS"
            log_success "AI dependencies installed"
        fi
    fi
    log_success "Python dependencies installed"
}

setup_ros2_workspace() {
    log_section "SETTING UP ROS 2 WORKSPACE"
    mkdir -p "$WORKSPACE_DIR/src"
    cd "$WORKSPACE_DIR"
    
    [ ! -f "/etc/ros/rosdep/sources.list.d/20-default.list" ] && sudo rosdep init
    rosdep update
    log_success "Workspace configured"
}

configure_ros2_environment() {
    log_section "CONFIGURING ROS 2 ENVIRONMENT"
    cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d_%H%M%S)
    sed -i '/# ROS 2 Configuration/,/# End ROS 2 Configuration/d' ~/.bashrc
    
    cat >> ~/.bashrc << 'EOF'

# ROS 2 Configuration
source /opt/ros/humble/setup.bash
[ -f "$HOME/ros2_ws/install/local_setup.bash" ] && source $HOME/ros2_ws/install/local_setup.bash
source /usr/share/colcon_cd/function/colcon_cd.sh
export ROS_DOMAIN_ID=14
# End ROS 2 Configuration
EOF
    log_success "Environment configured"
}

build_workspace() {
    log_section "BUILDING WORKSPACE"
    cd "$WORKSPACE_DIR"
    source /opt/ros/humble/setup.bash
    rosdep install -i --from-path src --rosdistro humble -r -y
    colcon build --symlink-install
    log_success "Workspace built"
}

verify_installation() {
    log_section "VERIFYING INSTALLATION"
    source /opt/ros/humble/setup.bash
    [ -f "$WORKSPACE_DIR/install/local_setup.bash" ] && source "$WORKSPACE_DIR/install/local_setup.bash"
    
    command -v ros2 &> /dev/null && log_success "ROS 2: $ROS_DISTRO" || log_error "ROS 2 not found"
    python3 -c "import cv2, numpy, scipy; print('Python: OK')" 2>/dev/null || log_warning "Some Python packages missing"
    ros2 pkg list 2>/dev/null | grep -q "mirela_sdk" && log_success "mirela_sdk: OK" || log_warning "mirela_sdk not found"
    log_success "Verification complete"
}

main() {
    log_section "MIRELA SDK INSTALLATION"
    check_root
    check_distro
    
    echo "Select option:"
    echo "1) Full installation (recommended)"
    echo "2) Custom installation"
    echo "3) Verify installation"
    echo "4) Install RealSense support"
    read -p "Option [1]: " option
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
            echo "Select steps (space-separated, e.g., 1 3 5):"
            echo "1) Update system  2) Essential packages  3) Git/SSH"
            echo "4) ROS 2          5) GeographicLib       6) Clone repo"
            echo "7) Python deps    8) Setup workspace     9) Environment"
            echo "10) Build         11) Verify"
            read -p "Steps: " steps
            for step in $steps; do
                case $step in
                    1) update_system ;; 2) install_essential_packages ;;
                    3) configure_git_ssh ;; 4) install_ros2 ;;
                    5) configure_geographiclib ;; 6) clone_mirela_sdk ;;
                    7) install_python_dependencies ;; 8) setup_ros2_workspace ;;
                    9) configure_ros2_environment ;; 10) build_workspace ;;
                    11) verify_installation ;; *) log_warning "Invalid: $step" ;;
                esac
            done
            ;;
        3) verify_installation ;;
        4)
            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            if [ -f "$SCRIPT_DIR/install_realsense.sh" ]; then
                "$SCRIPT_DIR/install_realsense.sh"
            else
                log_error "install_realsense.sh not found"
                exit 1
            fi
            ;;
        *) log_error "Invalid option"; exit 1 ;;
    esac
    
    echo ""
    log_success "🐝 AVANTE! Run: source ~/.bashrc"
    log_info "Test: ros2 pkg list | grep mirela"
}

main "$@"
