#!/bin/bash
# Train Ultralytics YOLO models

set -e

# Default configuration
MODEL="yolov8n.pt"
DATASET=""
OUTPUT_DIR="outputs/ultralytics"
EPOCHS=100
BATCH_SIZE=16
LEARNING_RATE=0.01
DEVICE="cuda"
IMGSZ=640
SEED=42
TENSORBOARD=true
EVAL=true
EVAL_SPLIT="test"
CONF_THRESHOLD=0.25
IOU_THRESHOLD=0.5
PUSH_TO_HUB=false
HUB_MODEL_ID=""
MULTI_GPU=false
MIXED_PRECISION="no"
GRADIENT_ACCUMULATION=1
MAX_TRAIN_SAMPLES=""
MAX_EVAL_SAMPLES=""
EARLY_STOPPING_PATIENCE=""
FROM_SCRATCH=false

show_help() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Train Ultralytics YOLO models"
    echo ""
    echo "Required:"
    echo "  --dataset PATH           Path to dataset (YOLO format data.yaml)"
    echo ""
    echo "Options:"
    echo "  --model NAME             Model name (default: $MODEL)"
    echo "  --output-dir DIR         Output directory (default: $OUTPUT_DIR)"
    echo "  --epochs NUM             Training epochs (default: $EPOCHS)"
    echo "  --batch-size NUM         Batch size (default: $BATCH_SIZE)"
    echo "  --learning-rate NUM      Learning rate (default: $LEARNING_RATE)"
    echo "  --device DEVICE          Device (default: $DEVICE)"
    echo "  --imgsz NUM              Image size (default: $IMGSZ)"
    echo "  --seed NUM               Random seed (default: $SEED)"
    echo "  --no-tensorboard         Disable TensorBoard"
    echo "  --no-eval                Skip evaluation after training"
    echo "  --eval-split SPLIT       Evaluation split (default: $EVAL_SPLIT)"
    echo "  --conf-threshold NUM     Confidence threshold (default: $CONF_THRESHOLD)"
    echo "  --iou-threshold NUM      IoU threshold (default: $IOU_THRESHOLD)"
    echo "  --push-to-hub            Push model to HuggingFace Hub"
    echo "  --hub-model-id ID        HuggingFace model ID"
    echo "  --multi-gpu              Enable multi-GPU training"
    echo "  --mixed-precision MODE   Mixed precision (no, fp16)"
    echo "  --gradient-accumulation N  Gradient accumulation steps"
    echo "  --max-train-samples NUM  Max training samples"
    echo "  --max-eval-samples NUM   Max evaluation samples"
    echo "  --early-stopping NUM     Early stopping patience"
    echo "  --from-scratch           Train from scratch"
    echo ""
    exit 0
}

[ "$1" = "--help" ] || [ "$1" = "-h" ] && show_help

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --dataset) DATASET="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --epochs) EPOCHS="$2"; shift 2 ;;
        --batch-size) BATCH_SIZE="$2"; shift 2 ;;
        --learning-rate) LEARNING_RATE="$2"; shift 2 ;;
        --device) DEVICE="$2"; shift 2 ;;
        --imgsz) IMGSZ="$2"; shift 2 ;;
        --seed) SEED="$2"; shift 2 ;;
        --no-tensorboard) TENSORBOARD=false; shift ;;
        --no-eval) EVAL=false; shift ;;
        --eval-split) EVAL_SPLIT="$2"; shift 2 ;;
        --conf-threshold) CONF_THRESHOLD="$2"; shift 2 ;;
        --iou-threshold) IOU_THRESHOLD="$2"; shift 2 ;;
        --push-to-hub) PUSH_TO_HUB=true; shift ;;
        --hub-model-id) HUB_MODEL_ID="$2"; shift 2 ;;
        --multi-gpu) MULTI_GPU=true; shift ;;
        --mixed-precision) MIXED_PRECISION="$2"; shift 2 ;;
        --gradient-accumulation) GRADIENT_ACCUMULATION="$2"; shift 2 ;;
        --max-train-samples) MAX_TRAIN_SAMPLES="$2"; shift 2 ;;
        --max-eval-samples) MAX_EVAL_SAMPLES="$2"; shift 2 ;;
        --early-stopping) EARLY_STOPPING_PATIENCE="$2"; shift 2 ;;
        --from-scratch) FROM_SCRATCH=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ -z "$DATASET" ]; then
    echo "Error: --dataset is required"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Build command
CMD="python -m mirela_sdk.ai.detection.cli.train \
    --framework ultralytics \
    --model $MODEL \
    --dataset $DATASET \
    --output-dir $OUTPUT_DIR \
    --epochs $EPOCHS \
    --batch-size $BATCH_SIZE \
    --learning-rate $LEARNING_RATE \
    --device $DEVICE \
    --imgsz $IMGSZ \
    --seed $SEED \
    --conf-threshold $CONF_THRESHOLD \
    --iou-threshold $IOU_THRESHOLD \
    --mixed-precision $MIXED_PRECISION \
    --gradient-accumulation-steps $GRADIENT_ACCUMULATION"

[ "$TENSORBOARD" = true ] && CMD="$CMD --tensorboard"
[ "$EVAL" = true ] && CMD="$CMD --evaluate --eval-split $EVAL_SPLIT"
[ "$PUSH_TO_HUB" = true ] && CMD="$CMD --push-to-hub"
[ -n "$HUB_MODEL_ID" ] && CMD="$CMD --hub-model-id $HUB_MODEL_ID"
[ "$MULTI_GPU" = true ] && CMD="$CMD --multi-gpu"
[ -n "$MAX_TRAIN_SAMPLES" ] && CMD="$CMD --max-train-samples $MAX_TRAIN_SAMPLES"
[ -n "$MAX_EVAL_SAMPLES" ] && CMD="$CMD --max-eval-samples $MAX_EVAL_SAMPLES"
[ -n "$EARLY_STOPPING_PATIENCE" ] && CMD="$CMD --early-stopping-patience $EARLY_STOPPING_PATIENCE"
[ "$FROM_SCRATCH" = true ] && CMD="$CMD --from-scratch"

echo "=" 
echo "Training Ultralytics YOLO"
echo "  Model: $MODEL"
echo "  Dataset: $DATASET"
echo "  Output: $OUTPUT_DIR"
echo "="

$CMD

echo "Training complete! Results in $OUTPUT_DIR"
