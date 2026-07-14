#!/usr/bin/env bash
# Smoke-test nectar-ai classify CLI
set -euo pipefail

AI=(python -m nectar.ai.cli.main)
if command -v nectar-ai >/dev/null 2>&1; then
  AI=(nectar-ai)
fi

"${AI[@]}" classify --help >/dev/null
"${AI[@]}" classify train --help >/dev/null
"${AI[@]}" classify predict --help >/dev/null
"${AI[@]}" classify eval --help >/dev/null
"${AI[@]}" classify dataset --help >/dev/null

echo "nectar-ai classify CLI smoke OK"

# Optional: predict if a model weight is available / downloadable
if [[ "${RUN_PREDICT:-0}" == "1" ]]; then
  TMP="$(mktemp -d)"
  python - <<'PY' "$TMP"
import sys
from pathlib import Path
import numpy as np
import cv2
out = Path(sys.argv[1]) / "sample.jpg"
img = (np.random.rand(224, 224, 3) * 255).astype("uint8")
cv2.imwrite(str(out), img)
print(out)
PY
  IMG="$TMP/sample.jpg"
  "${AI[@]}" classify predict --model yolo26n-cls.pt --input "$IMG" --output "$TMP/pred"
  echo "predict OK → $TMP/pred"
fi
