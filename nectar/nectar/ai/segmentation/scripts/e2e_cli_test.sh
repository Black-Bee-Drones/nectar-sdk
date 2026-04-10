#!/bin/bash
# ==========================================================================
# End-to-end CLI test for the segmentation module
#
# Tests: download -> analyze -> train -> eval -> predict
#
# Frameworks: Ultralytics (YOLO26n-seg), RF-DETR (Seg Nano)
#
# Each training run uses a YAML config, TensorBoard logging, post-train
# evaluation, and HuggingFace Hub upload.
#
# Designed for a GTX 1650 (4 GB VRAM): small batch, low resolution, few
# epochs, and subsets where needed.
# ==========================================================================
set -e

export PYTHONPATH=/home/samuel/ros2_ws/src/nectar-sdk/nectar:$PYTHONPATH
export HF_TOKEN="${HF_TOKEN:-}"
cd /home/samuel/ros2_ws/src/nectar-sdk/nectar

AI_DIR=nectar/ai
DATA_DIR=$AI_DIR/data
OUTPUT_DIR=$AI_DIR/outputs
CONFIGS=$AI_DIR/segmentation/configs

sep() { echo ""; echo "============================================================"; echo "$1"; echo "============================================================"; }

# ------------------------------------------------------------------
# 1. Download
# ------------------------------------------------------------------
sep "STEP 1: Download crack-seg dataset"

if [ -f "$DATA_DIR/crack-seg/data.yaml" ]; then
  echo "Dataset already present, skipping download."
else
  nectar-ai segment dataset download \
    --source ultralytics \
    --dataset crack-seg \
    --output $DATA_DIR/crack-seg \
    --format yolo
fi

for split in train valid test; do
  n=$(ls "$DATA_DIR/crack-seg/$split/images/" 2>/dev/null | wc -l)
  echo "  $split: $n images"
done

# ------------------------------------------------------------------
# 2. Analyze
# ------------------------------------------------------------------
sep "STEP 2: Analyze dataset"

nectar-ai segment dataset analyze \
  --input $DATA_DIR/crack-seg \
  --output $DATA_DIR/crack-seg/analysis

echo "Analysis outputs:"
ls $DATA_DIR/crack-seg/analysis/

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

  nectar-ai segment train --config "$config_file"

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

  local rfdetr_args=""
  if [ "$framework" = "rfdetr" ]; then
    rfdetr_args="--rfdetr-size nano --resolution 312"
  fi

  nectar-ai segment eval \
    --model-path "$best" \
    --dataset-path $DATA_DIR/crack-seg \
    --framework "$framework" \
    --output-dir "$run_dir/eval-standalone" \
    --split test \
    --conf-threshold 0.25 \
    --iou-threshold 0.5 \
    --device 0 \
    --batch-size 1 \
    $rfdetr_args

  echo "Eval outputs ($(ls "$run_dir/eval-standalone/" | wc -l) files):"
  ls "$run_dir/eval-standalone/"

  # Predict
  sep "PREDICT: $name"

  local test_img=$(ls $DATA_DIR/crack-seg/test/images/*.jpg 2>/dev/null | head -1)
  nectar-ai segment predict \
    --model "$best" \
    --input "$test_img" \
    --output "$run_dir/predictions" \
    --device 0 \
    --conf-threshold 0.25 \
    --save-masks

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
# 3. Ultralytics (YOLO26n-seg)
# ------------------------------------------------------------------
run_experiment "crackseg-yolo26n-seg" "$CONFIGS/crackseg_yolo26n_seg.yaml" "ultralytics"

# ------------------------------------------------------------------
# 4. RF-DETR Seg Nano
# ------------------------------------------------------------------
run_experiment "crackseg-rfdetr-seg-nano" "$CONFIGS/crackseg_rfdetr_seg_nano.yaml" "rfdetr"

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
sep "ALL EXPERIMENTS COMPLETED"

echo "Data:    $DATA_DIR/crack-seg/"
echo ""
echo "Runs:"
for run in crackseg-yolo26n-seg crackseg-rfdetr-seg-nano; do
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
