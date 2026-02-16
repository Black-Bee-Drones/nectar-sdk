#!/bin/bash
# Train RF-DETR models

set -e

# Default configuration
MODEL="rfdetr-base"
DATASET=""
OUTPUT_DIR="outputs/rfdetr"
EPOCHS=50
BATCH_SIZE=4
LEARNING_RATE=1e-4
DEVICE="cuda"
RESOLUTION=728
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
GRADIENT_ACCUMULATION=4
MAX_TRAIN_SAMPLES=""
MAX_EVAL_SAMPLES=""
EARLY_STOPPING_PATIENCE=""
WEIGHT_DECAY=1e-4
USE_EMA=true
GRADIENT_CHECKPOINTING=false
CONFIG=""

show_help() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Train RF-DETR models"
    echo ""
    echo "Options:"
    echo "  --config FILE            Path to YAML config file"
    echo "  --dataset PATH           Path to COCO format dataset"
    echo "  --model NAME             Model size: rfdetr-{nano,small,base,medium,large}"
    echo "                           (default: $MODEL)"
    echo "  --output-dir DIR         Output directory (default: $OUTPUT_DIR)"
    echo "  --epochs NUM             Training epochs (default: $EPOCHS)"
    echo "  --batch-size NUM         Batch size (default: $BATCH_SIZE)"
    echo "  --learning-rate NUM      Learning rate (default: $LEARNING_RATE)"
    echo "  --device DEVICE          Device (default: $DEVICE)"
    echo "  --resolution NUM         Image resolution (divisible by 56, default: $RESOLUTION)"
    echo "  --seed NUM               Random seed (default: $SEED)"
    echo "  --no-tensorboard         Disable TensorBoard"
    echo "  --no-eval                Skip evaluation after training"
    echo "  --push-to-hub            Push model to HuggingFace Hub"
    echo "  --hub-model-id ID        HuggingFace model ID"
    echo "  --multi-gpu              Enable multi-GPU training"
    echo "  --mixed-precision MODE   Mixed precision (no, fp16)"
    echo "  --gradient-accumulation N  Gradient accumulation steps"
    echo "  --early-stopping NUM     Early stopping patience"
    echo "  --no-ema                 Disable EMA"
    echo "  --gradient-checkpointing Enable gradient checkpointing"
    echo ""
    echo "Examples:"
    echo "  # Using config file"
    echo "  ./train_rfdetr.sh --config configs/rfdetr_example.yaml"
    echo ""
    echo "  # Using CLI arguments"
    echo "  ./train_rfdetr.sh --dataset /path/to/coco --epochs 100"
    echo ""
    exit 0
}

[ "$1" = "--help" ] || [ "$1" = "-h" ] && show_help

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --dataset) DATASET="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --epochs) EPOCHS="$2"; shift 2 ;;
        --batch-size) BATCH_SIZE="$2"; shift 2 ;;
        --learning-rate) LEARNING_RATE="$2"; shift 2 ;;
        --device) DEVICE="$2"; shift 2 ;;
        --resolution) RESOLUTION="$2"; shift 2 ;;
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
        --weight-decay) WEIGHT_DECAY="$2"; shift 2 ;;
        --no-ema) USE_EMA=false; shift ;;
        --gradient-checkpointing) GRADIENT_CHECKPOINTING=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Functions to extract config values
get_config_value() {
    local key="$1"
    local section="$2"
    if [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
        python3 -c "
import yaml
try:
    with open('$CONFIG', 'r') as f:
        config = yaml.safe_load(f)
    value = config.get('$section', {}).get('$key')
    if value is not None:
        print(value)
except Exception:
    pass
" 2>/dev/null
    fi
}

# If config file provided, use it directly with Python CLI
if [ -n "$CONFIG" ]; then
    echo "Using config file: $CONFIG"

    # Extract multi_gpu from config
    CONFIG_MULTI_GPU=$(get_config_value multi_gpu train)
    CONFIG_DEVICE=$(get_config_value device train)

    [ "$CONFIG_MULTI_GPU" = "True" ] && MULTI_GPU=true
    [ -n "$CONFIG_DEVICE" ] && DEVICE="$CONFIG_DEVICE"

    # Build command with config
    TRAIN_CMD="mirela_sdk.ai.detection.cli.train --config $CONFIG"

    if [ "$MULTI_GPU" = true ]; then
        echo "Multi-GPU training enabled"
        GPU_COUNT=$(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null || echo "1")
        echo "Using $GPU_COUNT GPUs"
        torchrun --nproc-per-node=$GPU_COUNT -m $TRAIN_CMD
    else
        # Single GPU
        if [[ "$DEVICE" =~ ^cuda:([0-9]+)$ ]]; then
            export CUDA_VISIBLE_DEVICES="${BASH_REMATCH[1]}"
        else
            export CUDA_VISIBLE_DEVICES="0"
        fi

        python -m $TRAIN_CMD
    fi

    exit $?
fi

# CLI mode - require dataset
if [ -z "$DATASET" ]; then
    echo "Error: --dataset or --config is required"
    exit 1
fi

# Validate resolution is divisible by 56
if (( RESOLUTION % 56 != 0 )); then
    echo "Warning: Resolution $RESOLUTION not divisible by 56"
fi

mkdir -p "$OUTPUT_DIR"

# Build command
TRAIN_CMD="mirela_sdk.ai.detection.cli.train \
    --framework rfdetr \
    --model $MODEL \
    --dataset $DATASET \
    --output-dir $OUTPUT_DIR \
    --epochs $EPOCHS \
    --batch-size $BATCH_SIZE \
    --learning-rate $LEARNING_RATE \
    --device $DEVICE \
    --imgsz $RESOLUTION \
    --seed $SEED \
    --conf-threshold $CONF_THRESHOLD \
    --iou-threshold $IOU_THRESHOLD \
    --mixed-precision $MIXED_PRECISION \
    --gradient-accumulation-steps $GRADIENT_ACCUMULATION \
    --weight-decay $WEIGHT_DECAY"

[ "$TENSORBOARD" = true ] && TRAIN_CMD="$TRAIN_CMD --tensorboard"
[ "$EVAL" = true ] && TRAIN_CMD="$TRAIN_CMD --evaluate --eval-split $EVAL_SPLIT"
[ "$PUSH_TO_HUB" = true ] && TRAIN_CMD="$TRAIN_CMD --push-to-hub"
[ -n "$HUB_MODEL_ID" ] && TRAIN_CMD="$TRAIN_CMD --hub-model-id $HUB_MODEL_ID"
[ "$MULTI_GPU" = true ] && TRAIN_CMD="$TRAIN_CMD --multi-gpu"
[ -n "$MAX_TRAIN_SAMPLES" ] && TRAIN_CMD="$TRAIN_CMD --max-train-samples $MAX_TRAIN_SAMPLES"
[ -n "$MAX_EVAL_SAMPLES" ] && TRAIN_CMD="$TRAIN_CMD --max-eval-samples $MAX_EVAL_SAMPLES"
[ -n "$EARLY_STOPPING_PATIENCE" ] && TRAIN_CMD="$TRAIN_CMD --early-stopping-patience $EARLY_STOPPING_PATIENCE"

echo "="
echo "Training RF-DETR"
echo "  Model: $MODEL"
echo "  Dataset: $DATASET"
echo "  Output: $OUTPUT_DIR"
echo "  Resolution: $RESOLUTION"
echo "="

# Multi-GPU with torchrun
if [ "$MULTI_GPU" = true ]; then
    GPU_COUNT=$(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null || echo "1")
    echo "Using $GPU_COUNT GPUs with torchrun"
    torchrun --nproc-per-node=$GPU_COUNT -m $TRAIN_CMD
else
    # Single GPU
    if [[ "$DEVICE" =~ ^cuda:([0-9]+)$ ]]; then
        export CUDA_VISIBLE_DEVICES="${BASH_REMATCH[1]}"
    else
        export CUDA_VISIBLE_DEVICES="0"
    fi

    python -m $TRAIN_CMD
fi

echo "Training complete! Results in $OUTPUT_DIR"
