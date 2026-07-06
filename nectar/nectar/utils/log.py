"""ANSI color/symbol helpers for log messages.

Auto-disabled when stderr is not a TTY, ``NO_COLOR`` is set, or
``RCUTILS_COLORIZED_OUTPUT=0`` (ROS2 convention).
"""

import os
import sys

_ENABLED = (
    sys.stderr.isatty()
    and "NO_COLOR" not in os.environ
    and os.environ.get("RCUTILS_COLORIZED_OUTPUT", "1") != "0"
)


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _ENABLED else text


OK = _c("✓", "32")  # green check
ERR = _c("✗", "31")  # red cross
WARN = _c("⚠", "33")  # yellow warning
ARROW = _c("→", "36")  # cyan arrow
