#!/bin/bash

_pip_flags() {
    if [[ "${NON_INTERACTIVE:-}" == "true" ]] && [[ $EUID -eq 0 ]]; then
        echo "--ignore-installed"
    fi
}

cmd_python() {
    local extra="${1:-}"
    local flags
    flags=$(_pip_flags)
    log_section "INSTALLING PYTHON DEPENDENCIES"
    python3 -m pip install --upgrade pip

    if [[ -z "$extra" ]]; then
        log_info "Installing core dependencies..."
        cd "$PKG_DIR" && python3 -m pip install $flags -e "."
    else
        log_info "Installing [$extra] dependencies..."
        cd "$PKG_DIR" && python3 -m pip install $flags -e ".[$extra]"
    fi
    log_success "Python dependencies installed ($extra)"
}

# Usage: cmd_pytorch [variant]
#   variant: cpu, cu124, cu118, auto (default: auto)
#   auto = detect nvidia-smi → cu124, else cpu
cmd_pytorch() {
    local variant="${1:-auto}"

    if [[ "$variant" == "auto" ]]; then
        if command -v nvidia-smi &>/dev/null; then
            variant="cu124"
            log_info "NVIDIA GPU detected"
        else
            variant="cpu"
            log_info "No NVIDIA GPU detected"
        fi
    fi

    local index="https://download.pytorch.org/whl/${variant}"

    log_section "INSTALLING PYTORCH (${variant})"
    log_info "torch==${PYTORCH_VERSION} torchvision==${TORCHVISION_VERSION}"
    log_info "Index: ${index}"

    python3 -m pip install \
        "torch==${PYTORCH_VERSION}" \
        "torchvision==${TORCHVISION_VERSION}" \
        --index-url "$index"

    log_success "PyTorch ${variant} installed"
}
