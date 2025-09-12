#!/bin/bash

# Build script for MIRELA SDK Docker images
# Usage: ./build_images.sh [base|realsense|all]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Function to build base image
build_base() {
    log_info "Construindo imagem base mirela-sdk:base..."
    docker build --network=host -t mirela-sdk:base -f Dockerfile.base .
    log_success "Imagem base construída com sucesso!"
}

# Function to build RealSense image
build_realsense() {
    log_info "Verificando se imagem base existe..."
    if ! docker image inspect mirela-sdk:base >/dev/null 2>&1; then
        log_warning "Imagem base não encontrada, construindo primeiro..."
        build_base
    fi

    log_info "Construindo imagem RealSense mirela-sdk:realsense..."
    docker build --network=host -t mirela-sdk:realsense -f Dockerfile.realsense .
    log_success "Imagem RealSense construída com sucesso!"
}

# Function to build all images
build_all() {
    log_info "Construindo todas as imagens..."
    build_base
    build_realsense
    log_success "Todas as imagens construídas!"
}

# Function to show usage
usage() {
    echo "Uso: $0 [opção]"
    echo "Opções:"
    echo "  base       Construir apenas imagem base"
    echo "  realsense  Construir apenas imagem RealSense"
    echo "  all        Construir todas as imagens (padrão)"
    echo "  --help     Mostrar esta ajuda"
}

# Main script
case "${1:-all}" in
    "base")
        build_base
        ;;
    "realsense")
        build_realsense
        ;;
    "all")
        build_all
        ;;
    "--help"|"-h")
        usage
        ;;
    *)
        log_error "Opção inválida: $1"
        usage
        exit 1
        ;;
esac

echo ""
log_success "🚀🐝 Construção concluída!"
echo "Para executar:"
echo "  Base:     ./run_docker_linux.sh --base"
echo "  RealSense: ./run_docker_linux.sh --realsense"
