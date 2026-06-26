#!/bin/bash

_ensure_uv() {
    if has_command uv; then return 0; fi
    log_info "Installing uv (fast Python package manager)..."
    if [[ $EUID -eq 0 ]]; then
        curl -LsSf https://astral.sh/uv/install.sh \
            | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
    else
        curl -LsSf https://astral.sh/uv/install.sh | env INSTALLER_NO_MODIFY_PATH=1 sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    has_command uv || { log_error "uv installation failed"; return 1; }
    log_success "uv installed ($(uv --version 2>/dev/null))"
}

# Create the shared workspace virtual environment if absent
_ensure_venv() {
    _ensure_uv || return 1
    if [ ! -f "$NECTAR_VENV/bin/activate" ]; then
        log_info "Creating shared workspace venv: ${NECTAR_VENV} (--system-site-packages)"
        uv venv "$NECTAR_VENV" --system-site-packages --seed --prompt nectar --python "$(command -v python3)"
    fi
}

# Activate the shared venv into the current shell if it exists
_activate_venv() {
    [ -f "$NECTAR_VENV/bin/activate" ] && source "$NECTAR_VENV/bin/activate"
    return 0
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
    "${NECTAR_VENV}/bin/python" -c "
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
    _ensure_venv || return 1
    _activate_venv
    log_section "INSTALLING PYTHON DEPENDENCIES"

    local torch_flags=""
    if [[ "$extra" == "ai" || "$extra" == "full" ]]; then
        torch_flags=$(_torch_constraint_flags)
        if [[ -n "$torch_flags" ]]; then
            log_info "Using PyTorch constraints: ${TORCH_CONSTRAINTS_FILE}"
        fi
    fi

    if [[ -z "$extra" ]]; then
        log_info "Installing core dependencies..."
        cd "$PKG_DIR" && uv pip install --python "$NECTAR_VENV/bin/python" $torch_flags -e "."
    else
        log_info "Installing [$extra] dependencies..."
        cd "$PKG_DIR" && uv pip install --python "$NECTAR_VENV/bin/python" $torch_flags -e ".[$extra]"
    fi
    log_success "Python dependencies installed (${extra:-core})"
}

# Usage: cmd_pytorch [backend]
#   backend: auto (default), cpu, cu118, cu126, cu128, cu130, ...  (uv --torch-backend)
#   auto = uv queries the CUDA driver and picks the matching wheel index
#          (CUDA 13 -> cu130), or falls back to cpu when no GPU is present.
#
# Uses uv's native PyTorch integration, which routes torch + its nvidia-* CUDA
# deps to the correct download.pytorch.org index (avoiding slow/timeout-prone
# pulls from pypi.nvidia.com). See https://docs.astral.sh/uv/guides/integration/pytorch/
#
# Env-var overrides (advanced):
#   TORCH_VERSION       Pin a specific torch version       (default in config.sh)
#   TORCHVISION_VERSION Pin a matching torchvision         (default in config.sh)
#   UV_HTTP_TIMEOUT     Per-request timeout (default 600s; raise on slow links)
#   UV_CONCURRENT_DOWNLOADS=1   Serialize downloads on very flaky networks
cmd_pytorch() {
    local backend="${1:-${TORCH_VARIANT:-auto}}"
    _ensure_venv || return 1
    _activate_venv

    log_section "INSTALLING PYTORCH (backend=${backend})"
    log_info "uv --torch-backend (auto-detects the CUDA driver when 'auto')"

    local torch_spec="torch"
    local vision_spec="torchvision"
    if [[ -n "${TORCH_VERSION:-}" ]]; then
        torch_spec="torch==${TORCH_VERSION}"
        vision_spec="torchvision==${TORCHVISION_VERSION:-}"
        [[ -z "${TORCHVISION_VERSION:-}" ]] && vision_spec="torchvision"
        log_info "Pinned: ${torch_spec}  ${vision_spec}"
    fi

    uv pip install --python "$NECTAR_VENV/bin/python" \
        --torch-backend="${backend}" \
        "${torch_spec}" "${vision_spec}"

    _save_torch_constraints
    # Record the resolved wheel index (from the installed +local tag, e.g.
    # cu130 / cpu) so a later [ai] install can pin to the same build if needed.
    "${NECTAR_VENV}/bin/python" -c "
import torch, pathlib
tag = torch.__version__.split('+')[-1] if '+' in torch.__version__ else 'cpu'
pathlib.Path('${TORCH_INDEX_FILE}').write_text(f'https://download.pytorch.org/whl/{tag}\n')
" 2>/dev/null || true

    log_success "PyTorch installed (backend=${backend})"

    "${NECTAR_VENV}/bin/python" -c "
import torch
print(f'  torch   {torch.__version__}  CUDA: {torch.cuda.is_available()}')
import torchvision
print(f'  vision  {torchvision.__version__}')
" 2>/dev/null || true
}
