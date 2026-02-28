"""Unified CLI for detection module.

Usage:
    nectar-od <command> [options]

Commands:
    train     Train a detection model
    predict   Run inference on images
    eval      Evaluate a model on a dataset
    dataset   Dataset management (download, convert, analyze, ...)
"""

import sys

COMMANDS = {
    "train": "nectar.ai.detection.cli.train",
    "predict": "nectar.ai.detection.cli.predict",
    "eval": "nectar.ai.detection.cli.evaluate",
    "dataset": "nectar.ai.detection.cli.dataset",
}

HELP_TEXT = """\
Usage: nectar-od <command> [options]

Commands:
  train     Train a detection model
  predict   Run inference on images
  eval      Evaluate a model on a dataset
  dataset   Dataset management (download, convert, analyze, ...)

Run 'nectar-od <command> --help' for command-specific options."""


def main():
    """Main entry point for unified CLI."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(HELP_TEXT)
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    command = sys.argv[1]

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print(HELP_TEXT)
        sys.exit(1)

    # Strip the top-level command so each submodule sees its own args
    sys.argv = sys.argv[1:]

    import importlib
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    module = importlib.import_module(COMMANDS[command])
    module.main()


if __name__ == "__main__":
    main()
