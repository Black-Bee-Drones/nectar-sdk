#!/bin/bash

_pip_flags() {
    local flags=""
    if [[ "${NON_INTERACTIVE:-}" == "true" ]] && [[ $EUID -eq 0 ]]; then
        flags="--ignore-installed"
    fi
    if [ -f /usr/lib/python3.*/EXTERNALLY-MANAGED ] 2>/dev/null; then
        flags="$flags --break-system-packages"
    fi
    echo "$flags"
}

_detect_cuda_version() {
    if ! command -v nvidia-smi &>/dev/null; then
        echo ""
        return
    fi
    nvidia-smi 2>/dev/null \
        | grep -oP 'CUDA Version:\s*\K[0-9]+\.[0-9]+' \
        | head -1
}

_cuda_to_torch_variant() {
    local cuda_ver="$1"           
    local major minor
    major="${cuda_ver%%.*}"
    minor="${cuda_ver#*.}"

    if [[ "$major" -lt 11 ]]; then
        echo "cpu" 
    elif [[ "$major" -eq 11 ]]; then
        echo "cu118"
    elif [[ "$major" -eq 12 ]]; then
        if   [[ "$minor" -le 1 ]]; then echo "cu121"
        elif [[ "$minor" -le 4 ]]; then echo "cu124"
        else                             echo "cu126"
        fi
    else
        echo "cu126"
    fi
}

_save_torch_constraints() {
    local dest="${TORCH_CONSTRAINTS_FILE}"
    log_info "Saving PyTorch constraints → ${dest}"
    python3 -c "
import importlib, sys, pathlib
lines = []
for pkg in ('torch', 'torchvision'):
    try:
        mod = importlib.import_module(pkg)
        lines.append(f'{pkg}=={mod.__version__}')
    except ImportError:
        pass
pathlib.Path('${dest}').write_text('\n'.join(lines) + '\n')
print('  ' + '  '.join(lines))
"
}

_torch_constraint_flags() {
    local flags=""
    if [[ -f "${TORCH_CONSTRAINTS_FILE}" ]]; then
        flags="--constraint ${TORCH_CONSTRAINTS_FILE}"
        if [[ -f "${TORCH_INDEX_FILE}" ]]; then
            local idx
            idx=$(cat "${TORCH_INDEX_FILE}")
            flags="${flags} --extra-index-url ${idx}"
        fi
    fi
    echo "$flags"
}


# Usage: cmd_python [extra]
#   extra: control, vision, ai, interface, all, full  (empty = core only)
cmd_python() {
    local extra="${1:-}"
    local flags
    flags=$(_pip_flags)
    log_section "INSTALLING PYTHON DEPENDENCIES"
    python3 -m pip install --upgrade pip $flags

    local torch_flags=""
    if [[ "$extra" == "ai" || "$extra" == "full" ]]; then
        torch_flags=$(_torch_constraint_flags)
        if [[ -n "$torch_flags" ]]; then
            log_info "Using PyTorch constraints: ${TORCH_CONSTRAINTS_FILE}"
        fi
    fi

    if [[ -z "$extra" ]]; then
        log_info "Installing core dependencies..."
        cd "$PKG_DIR" && python3 -m pip install $flags $torch_flags -e "."
    else
        log_info "Installing [$extra] dependencies..."
        cd "$PKG_DIR" && python3 -m pip install $flags $torch_flags -e ".[$extra]"
    fi
    log_success "Python dependencies installed (${extra:-core})"
}

# Usage: cmd_pytorch [variant]
#   variant: cpu, cu118, cu121, cu124, cu126, auto (default: auto)
#   auto = parse nvidia-smi CUDA version → best matching index, else cpu
#
# Env-var overrides (advanced):
#   TORCH_VERSION       Pin a specific torch version  (e.g. "2.7.1")
#   TORCHVISION_VERSION Pin a specific torchvision    (e.g. "0.22.1")
cmd_pytorch() {
    local variant="${1:-auto}"
    local flags
    flags=$(_pip_flags)

    if [[ "$variant" == "auto" ]]; then
        local cuda_ver
        cuda_ver=$(_detect_cuda_version)
        if [[ -n "$cuda_ver" ]]; then
            variant=$(_cuda_to_torch_variant "$cuda_ver")
            log_info "NVIDIA GPU detected — CUDA ${cuda_ver} → ${variant}"
        else
            variant="cpu"
            log_info "No NVIDIA GPU detected → CPU"
        fi
    fi

    local index="https://download.pytorch.org/whl/${variant}"

    log_section "INSTALLING PYTORCH (${variant})"
    log_info "Index: ${index}"

    local torch_spec="torch"
    local vision_spec="torchvision"
    if [[ -n "${TORCH_VERSION:-}" ]]; then
        torch_spec="torch==${TORCH_VERSION}"
        log_info "Pinned torch version: ${TORCH_VERSION}"
    fi
    if [[ -n "${TORCHVISION_VERSION:-}" ]]; then
        vision_spec="torchvision==${TORCHVISION_VERSION}"
        log_info "Pinned torchvision version: ${TORCHVISION_VERSION}"
    fi

    python3 -m pip install $flags \
        "${torch_spec}" "${vision_spec}" \
        --index-url "$index"

    _save_torch_constraints
    echo "$index" > "${TORCH_INDEX_FILE}"

    log_success "PyTorch ${variant} installed"

    python3 -c "
import torch
print(f'  torch   {torch.__version__}  CUDA: {torch.cuda.is_available()}')
import torchvision
print(f'  vision  {torchvision.__version__}')
" 2>/dev/null || true
}
