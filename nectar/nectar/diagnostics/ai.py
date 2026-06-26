"""AI functional checks.

The CLI entry point is exercised, a real nano-model inference is run on a
synthetic image (proving the detection pipeline end to end), and a CUDA tensor
op confirms GPU acceleration where a GPU build is present. Each self-skips when
torch is absent, no GPU is available, or model weights cannot be fetched.
"""

from __future__ import annotations

import sys

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec, Skip


def _nectar_ai_cli() -> str:
    from nectar.ai.cli import main as cli

    argv_backup = sys.argv
    sys.argv = ["nectar-ai", "--help"]
    code = None
    try:
        cli.main()
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.argv = argv_backup
    if code not in (0, None):
        raise Fail(f"`nectar-ai --help` exited with {code}")
    return "nectar-ai CLI entry point OK"


def _torch_cuda() -> str:
    try:
        import torch
    except ImportError:
        raise Skip("torch not installed (make pytorch)")
    if not torch.cuda.is_available():
        raise Skip(f"no usable CUDA (torch {torch.__version__}, cuda={torch.version.cuda})")
    tensor = torch.randn(128, 128, device="cuda")
    _ = float((tensor @ tensor).sum().cpu())
    return f"CUDA tensor op on {torch.cuda.get_device_name(0)} (torch {torch.__version__})"


def _nano_inference() -> str:
    try:
        import torch  # noqa: F401
    except ImportError:
        raise Skip("torch not installed (make pytorch)")
    helpers.require_module("ultralytics", "ultralytics not installed (make python-ai)")
    import numpy as np

    from nectar.ai.detection import DetectionResult, Detector

    detector = Detector("yolov8n.pt")
    try:
        detector.load()
    except Exception as exc:
        raise Skip(f"yolov8n weights unavailable (offline?): {type(exc).__name__}")

    image = (np.random.rand(640, 640, 3) * 255).astype(np.uint8)
    result = detector.detect(image, conf=0.25)
    if not isinstance(result, DetectionResult):
        raise Fail(f"detect() returned {type(result).__name__}, expected DetectionResult")
    return (
        f"yolov8n inference OK: {len(result)} detection(s), {result.inference_time * 1000:.0f} ms"
    )


MODULE = ModuleSpec(
    key="ai",
    title="AI / detection",
    install="make python-ai && make pytorch",
    checks=[
        Check("nectar-ai CLI", _nectar_ai_cli),
        Check("torch CUDA tensor", _torch_cuda),
        Check("yolov8n nano inference", _nano_inference),
    ],
)
