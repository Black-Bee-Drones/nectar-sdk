#!/bin/bash
# ==========================================================================
# End-to-end CLI test for the detection module
#
# Tests: download -> train -> eval -> predict  (per framework)
#
# Frameworks: Ultralytics (YOLO26n), RF-DETR Nano, Transformers (DETR)
#
# Each training run uses a YAML config, TensorBoard logging, post-train
# evaluation, and HuggingFace Hub upload.
#
# Designed for a GTX 1650 (4 GB VRAM): small batch, low resolution, few
# epochs.
# ==========================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NECTAR_PKG="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
export PYTHONPATH="$NECTAR_PKG:$PYTHONPATH"
export HF_TOKEN="${HF_TOKEN:-}"
cd "$NECTAR_PKG"

AI_DIR=nectar/ai
DATA_DIR=$AI_DIR/data
OUTPUT_DIR=$AI_DIR/outputs
CONFIGS=$AI_DIR/detection/configs

ROBOFLOW_API_KEY="${ROBOFLOW_API_KEY:?Set ROBOFLOW_API_KEY env var}"
ROBOFLOW_WORKSPACE="black-bee-drones"
ROBOFLOW_PROJECT="imav-25-gate-sfbbq"
ROBOFLOW_VERSION=1

sep() { echo ""; echo "============================================================"; echo "$1"; echo "============================================================"; }

# ------------------------------------------------------------------
# 1. Download gate dataset from Roboflow
# ------------------------------------------------------------------
sep "STEP 1: Download gate dataset"

if [ -f "$DATA_DIR/imav-gate/data.yaml" ]; then
  echo "Dataset already present, skipping download."
else
  nectar-ai detect dataset download \
    --source roboflow \
    --api-key "$ROBOFLOW_API_KEY" \
    --workspace "$ROBOFLOW_WORKSPACE" \
    --project "$ROBOFLOW_PROJECT" \
    --version "$ROBOFLOW_VERSION" \
    --output "$DATA_DIR/imav-gate" \
    --format yolo
fi

for split in train valid test; do
  n=$(ls "$DATA_DIR/imav-gate/$split/images/" 2>/dev/null | wc -l)
  echo "  $split: $n images"
done

# ------------------------------------------------------------------
# Helper: verify TensorBoard event files exist
# ------------------------------------------------------------------
check_tensorboard() {
  local run_dir=$1
  local found=$(find "$run_dir" -name "events.out.tfevents.*" 2>/dev/null | head -1)
  if [ -n "$found" ]; then
    echo "  TensorBoard: OK ($(find "$run_dir" -name "events.out.tfevents.*" | wc -l) event files)"
  else
    echo "  TensorBoard: WARNING - no event files found"
  fi
}

# ------------------------------------------------------------------
# Helper: run a single framework experiment
# ------------------------------------------------------------------
run_experiment() {
  local name=$1
  local config_file=$2
  local framework=$3

  sep "TRAIN: $name ($framework via $config_file)"

  nectar-ai detect train --config "$config_file"

  local run_dir=$OUTPUT_DIR/$name

  echo ""
  echo "Training outputs:"
  ls "$run_dir/" 2>/dev/null || echo "(no output dir found)"

  check_tensorboard "$run_dir"

  # Find best checkpoint
  local best=""
  for candidate in \
    "$run_dir/weights/best.pt" \
    "$run_dir/checkpoint_best_total.pth" \
    "$run_dir/checkpoint_best_ema.pth" \
    "$run_dir/$name/pytorch_model.bin" \
    "$run_dir/$name"; do
    if [ -e "$candidate" ]; then
      best=$candidate
      break
    fi
  done

  if [ -z "$best" ]; then
    echo "WARNING: no checkpoint found for $name, skipping eval/predict"
    return
  fi
  echo "Best checkpoint: $best"

  # Standalone eval
  sep "EVAL: $name"

  local extra_args=""
  if [ "$framework" = "rfdetr" ]; then
    extra_args="--rfdetr-size nano --resolution 320"
  fi

  nectar-ai detect eval \
    --model-path "$best" \
    --dataset-path "$DATA_DIR/imav-gate" \
    --framework "$framework" \
    --output-dir "$run_dir/eval-standalone" \
    --split test \
    --conf-threshold 0.25 \
    --iou-threshold 0.5 \
    --device 0 \
    --batch-size 1 \
    $extra_args

  echo "Eval outputs ($(ls "$run_dir/eval-standalone/" | wc -l) files):"
  ls "$run_dir/eval-standalone/"

  # Predict
  sep "PREDICT: $name"

  local test_img=$(ls $DATA_DIR/imav-gate/test/images/*.jpg 2>/dev/null | head -1)
  if [ -z "$test_img" ]; then
    test_img=$(ls $DATA_DIR/imav-gate/valid/images/*.jpg 2>/dev/null | head -1)
  fi

  nectar-ai detect predict \
    --model "$best" \
    --input "$test_img" \
    --output "$run_dir/predictions" \
    --device 0 \
    --conf-threshold 0.25

  echo "Prediction outputs:"
  ls "$run_dir/predictions/"

  # Free GPU
  python3 -c "
import gc, torch
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()
" 2>/dev/null || true
}

# ------------------------------------------------------------------
# 2. Ultralytics (YOLO26n)
# ------------------------------------------------------------------
run_experiment "gate-yolo26n" "$CONFIGS/gate_yolo26n.yaml" "ultralytics"

# ------------------------------------------------------------------
# 3. RF-DETR Nano
# ------------------------------------------------------------------
run_experiment "gate-rfdetr-nano" "$CONFIGS/gate_rfdetr_nano.yaml" "rfdetr"

# ------------------------------------------------------------------
# 4. Transformers (DETR)
# ------------------------------------------------------------------
run_experiment "gate-detr" "$CONFIGS/gate_detr.yaml" "transformers"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
sep "ALL EXPERIMENTS COMPLETED"

echo "Data:    $DATA_DIR/imav-gate/"
echo ""
echo "Runs:"
for run in gate-yolo26n gate-rfdetr-nano gate-detr; do
  if [ -d "$OUTPUT_DIR/$run" ]; then
    echo "  $run/"
    [ -f "$OUTPUT_DIR/$run/eval-standalone/metrics_summary.json" ] && \
      python3 -c "
import json, sys
m = json.load(open('$OUTPUT_DIR/$run/eval-standalone/metrics_summary.json'))
print(f'    mAP@50={m[\"map50\"]:.4f}  P={m[\"precision\"]:.4f}  R={m[\"recall\"]:.4f}  F1={m[\"f1_score\"]:.4f}')
" 2>/dev/null || echo "    (no eval metrics)"
    check_tensorboard "$OUTPUT_DIR/$run"
  fi
done
