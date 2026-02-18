"""CLI tools for detection module."""

from nectar.ai.detection.cli.evaluate import main as evaluate_main
from nectar.ai.detection.cli.predict import main as predict_main
from nectar.ai.detection.cli.train import main as train_main
from nectar.ai.detection.cli.upload import main as upload_main

__all__ = [
    "train_main",
    "predict_main",
    "evaluate_main",
    "upload_main",
]
