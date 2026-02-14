#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]  $1${NC}"; }
log_success() { echo -e "${GREEN}[OK]    $1${NC}"; }
log_warning() { echo -e "${YELLOW}[WARN]  $1${NC}"; }
log_error()   { echo -e "${RED}[ERROR] $1${NC}"; }
log_section() { echo -e "\n${PURPLE}=== $1 ===${NC}\n"; }

# sudo wrapper: no-op when already root (Docker), real sudo otherwise
SUDO() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

check_not_root() {
    # Allow root in non-interactive mode (Docker / CI)
    if [[ $EUID -eq 0 ]] && [[ "${NON_INTERACTIVE:-}" != "true" ]]; then
        log_error "Do not run as root. Script will use sudo when needed."
        exit 1
    fi
}

check_distro() {
    command -v lsb_release &> /dev/null || SUDO apt-get install -y lsb-release
    local distro
    distro=$(lsb_release -si)
    local version
    version=$(lsb_release -sr)
    log_info "Detected: $distro $version"

    if [[ "$distro" != "Ubuntu" ]] && [[ "$distro" != "Debian" ]]; then
        log_warning "Only tested on Ubuntu/Debian"
        if [[ "${NON_INTERACTIVE:-}" != "true" ]]; then
            read -p "Continue anyway? (y/N): " -n 1 -r && echo
            [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
        fi
    fi
}

has_command() {
    command -v "$1" &> /dev/null
}
