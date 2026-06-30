"""AI functional tests.

The CLI entry point is exercised, a real nano-model inference is run on a
synthetic image (proving the detection pipeline end to end), and a CUDA tensor
op confirms GPU acceleration where a GPU build is present. Each self-skips when
torch is absent, no GPU is available, or model weights cannot be fetched.
"""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.ai


def test_nectar_ai_cli():
    """The nectar-ai CLI entry point parses --help and exits cleanly."""
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
    assert code in (0, None), f"`nectar-ai --help` exited with {code}"


@pytest.mark.gpu
def test_torch_cuda():
    """A CUDA tensor matmul runs when a usable GPU build of torch is present."""
    torch = pytest.importorskip("torch", reason="torch not installed (make pytorch)")
    if not torch.cuda.is_available():
        pytest.skip(f"no usable CUDA (torch {torch.__version__}, cuda={torch.version.cuda})")
    tensor = torch.randn(128, 128, device="cuda")
    _ = float((tensor @ tensor).sum().cpu())


@pytest.mark.slow
@pytest.mark.network
def test_nano_inference():
    """A yolov8n inference runs end to end on a synthetic image."""
    pytest.importorskip("torch", reason="torch not installed (make pytorch)")
    pytest.importorskip("ultralytics", reason="ultralytics not installed (make python-ai)")
    import numpy as np

    from nectar.ai.detection import DetectionResult, Detector

    detector = Detector("yolov8n.pt")
    try:
        detector.load()
    except Exception as exc:  # noqa: BLE001 - offline / weights unavailable
        pytest.skip(f"yolov8n weights unavailable (offline?): {type(exc).__name__}")

    image = (np.random.rand(640, 640, 3) * 255).astype(np.uint8)
    result = detector.detect(image, conf=0.25)
    assert isinstance(result, DetectionResult), f"detect() returned {type(result).__name__}"
