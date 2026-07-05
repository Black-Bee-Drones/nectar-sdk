# Configuration

Where the SDK reads its versions and paths from, and how to override them.

## Versions and package lists

All versions and package lists live in a single file:

```
scripts/lib/config.sh
```

Edit it to change the ROS distro, PyTorch version, librealsense version, apt package lists, and
more. Every script, the Makefile, and the Dockerfile read from this file, so a change here
propagates everywhere. Common per-invocation overrides (no edit needed):

| Variable | Controls |
|---|---|
| `ROS_DISTRO` | ROS 2 distribution (e.g. `humble`, `jazzy`, `kilted`) |
| `TORCH_VERSION` / `TORCHVISION_VERSION` | PyTorch pair (set both together) |
| `LIBREALSENSE_VERSION` / `REALSENSE_ROS_TAG` | RealSense stack versions |

## Python environment location

Python dependencies install into a shared workspace venv at `$WORKSPACE/.venv` (see
[Installation](index.md#python-environment)). Override its location with `NECTAR_VENV=/path`; an
already-active `VIRTUAL_ENV` is respected. Always let the SDK create the venv (it pins it to the
ROS `python3`) — a manual `uv venv` may pick a newer Python without wheels for some deps.

## Changing versions across the workspace

Because `scripts/lib/config.sh` is the single source, upgrading a dependency for the whole
workspace (SDK + your mission packages sharing the venv) is one edit followed by a re-run of the
relevant `make python*` / `make pytorch` / `make realsense` target.
