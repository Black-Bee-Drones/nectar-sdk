#!/usr/bin/env bash
# Train Ultralytics YOLO-cls via nectar-ai
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${1:-${SCRIPT_DIR}/../configs/mnist_yolo26n_cls.yaml}"
nectar-ai classify train --config "$CONFIG"
