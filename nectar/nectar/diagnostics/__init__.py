"""Functional verification harness for the Nectar SDK.

Run with ``python3 -m nectar.diagnostics`` (all modules) or
``python3 -m nectar.diagnostics vision control`` (a subset). See
:mod:`nectar.diagnostics.runner` for the design.
"""

from nectar.diagnostics.runner import (
    Check,
    Fail,
    ModuleSpec,
    Result,
    Skip,
    available_modules,
    run,
)

__all__ = [
    "Check",
    "Fail",
    "ModuleSpec",
    "Result",
    "Skip",
    "available_modules",
    "run",
]
