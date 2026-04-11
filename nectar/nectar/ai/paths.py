"""Shared path resolution for AI module data and outputs."""

from pathlib import Path
from typing import Optional


def _find_git_root(start_path: Path) -> Optional[Path]:
    current = start_path.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _get_ai_module_dir() -> Path:
    """Resolve the ``nectar/nectar/ai/`` directory from source or install."""
    installed_dir = Path(__file__).parent

    git_root = _find_git_root(Path(__file__))
    if git_root is None:
        return installed_dir

    candidates = [
        git_root / "nectar" / "nectar" / "ai",
        git_root / "nectar" / "ai",
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "__init__.py").exists():
            return candidate

    return installed_dir


AI_MODULE_DIR = _get_ai_module_dir()
DEFAULT_DATA_DIR = AI_MODULE_DIR / "data"
DEFAULT_OUTPUT_DIR = AI_MODULE_DIR / "outputs"
