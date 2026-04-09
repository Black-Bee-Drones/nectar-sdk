"""Unified CLI for Nectar AI modules.

Usage:
    nectar-ai <task> <command> [options]

Tasks:
    detect       Object detection (alias: detection, od)
    segment      Image segmentation (alias: segmentation, seg)

Commands:
    train     Train a model
    predict   Run inference on images
    eval      Evaluate a model on a dataset
    dataset   Dataset management (detection & segmentation)
"""

import sys

TASK_ALIASES = {
    "detection": "detection",
    "detect": "detection",
    "od": "detection",
    "segmentation": "segmentation",
    "segment": "segmentation",
    "seg": "segmentation",
}

TASK_COMMANDS = {
    "detection": {
        "train": "nectar.ai.detection.cli.train",
        "predict": "nectar.ai.detection.cli.predict",
        "eval": "nectar.ai.detection.cli.evaluate",
        "dataset": "nectar.ai.detection.cli.dataset",
    },
    "segmentation": {
        "train": "nectar.ai.segmentation.cli.train",
        "predict": "nectar.ai.segmentation.cli.predict",
        "eval": "nectar.ai.segmentation.cli.evaluate",
        "dataset": "nectar.ai.segmentation.cli.dataset",
    },
}

HELP_TEXT = """\
Usage: nectar-ai <task> <command> [options]

Tasks:
  detect       Object detection (aliases: detection, od)
  segment      Image segmentation (aliases: segmentation, seg)

Commands:
  train     Train a model
  predict   Run inference on images
  eval      Evaluate a model on a dataset
  dataset   Dataset management (detection & segmentation)

Examples:
  nectar-ai detect train --model yolov8n.pt --dataset /path/to/data
  nectar-ai detect predict --model yolov8n.pt --input image.jpg
  nectar-ai segment train --model yolov8n-seg.pt --dataset /path/to/data
  nectar-ai segment predict --model yolov8n-seg.pt --input image.jpg
  nectar-ai detect dataset download --source roboflow ...
  nectar-ai segment dataset download --source ultralytics --dataset crack-seg

Run 'nectar-ai <task> <command> --help' for command-specific options."""


def main():
    """Main entry point for the unified nectar-ai CLI."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(HELP_TEXT)
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    task_arg = sys.argv[1].lower()
    task = TASK_ALIASES.get(task_arg)

    if task is None:
        print(f"Unknown task: {task_arg}")
        print(HELP_TEXT)
        sys.exit(1)

    commands = TASK_COMMANDS[task]

    if len(sys.argv) < 3 or sys.argv[2] in ("-h", "--help"):
        available = ", ".join(commands.keys())
        print(f"Usage: nectar-ai {task_arg} <command> [options]")
        print(f"\nAvailable commands: {available}")
        print(f"\nRun 'nectar-ai {task_arg} <command> --help' for details.")
        sys.exit(0 if len(sys.argv) >= 3 else 1)

    command = sys.argv[2].lower()

    if command not in commands:
        available = ", ".join(commands.keys())
        print(f"Unknown command '{command}' for task '{task_arg}'.")
        print(f"Available commands: {available}")
        sys.exit(1)

    # Strip task and command args so the submodule sees only its own options
    sys.argv = [f"nectar-ai {task_arg} {command}"] + sys.argv[3:]

    import importlib
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    module = importlib.import_module(commands[command])
    module.main()


if __name__ == "__main__":
    main()
