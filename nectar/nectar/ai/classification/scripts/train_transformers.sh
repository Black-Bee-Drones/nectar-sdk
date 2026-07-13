#!/usr/bin/env bash
# Train HuggingFace ViT classification via nectar-ai
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${1:-${SCRIPT_DIR}/../configs/mnist_vit_example.yaml}"
nectar-ai classify train --config "$CONFIG"
