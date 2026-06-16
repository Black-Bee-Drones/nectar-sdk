# Contributing to Nectar SDK 🐝

Thank you for your interest in contributing! This guide will help you get started.

## Before You Start

Please discuss significant changes via [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues) or [Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) before implementation.

Read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## Issues and Feature Requests 🐛

### Reporting Bugs

Create bug reports that are:

- **Reproducible**: Include steps to reproduce the issue
- **Specific**: Version numbers, OS, hardware details
- **Unique**: Search existing issues first
- **Scoped**: One bug per report

### Feature Requests

Check [Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) for ongoing conversations before opening a new request.

## Development Setup

### Git LFS

This repository uses [Git LFS](https://git-lfs.github.com/) to track large binary files (images, videos, model weights, etc.). Install Git LFS before cloning:

```bash
git lfs install

git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
cd nectar-sdk
```

Git LFS automatically handles large files defined in `.gitattributes`. When you add images, videos, or other large files, they're automatically tracked by LFS.

**Note:** If you cloned before Git LFS was set up, you may need to pull LFS files:
```bash
git lfs pull
```

### Pre-commit Hooks

Install [pre-commit](https://pre-commit.com/) hooks (one-time setup):

```bash
pip install pre-commit
pre-commit install
```

After `pre-commit install`, hooks run **automatically on every `git commit`** — they check only staged files, auto-fix what they can, and abort the commit if changes were made. Just `git add` the fixes and commit again.

### Before Pushing

Always run the full check before pushing (same command CI runs):

```bash
make check
# or equivalently: pre-commit run --all-files
```

This validates **all files** (Python, Markdown, YAML, shell scripts) for:
- Trailing whitespace and missing end-of-file newlines
- Python lint errors (unused imports, undefined names)
- Import sorting
- Code formatting

### Quick Commands

```bash
make check       # run all checks (same as CI)
make lint        # Python lint only (ruff check)
make lint-fix    # Python lint + auto-fix (ruff check --fix)
make format      # Python format only (ruff format)
```

Use `make lint` / `make format` during development for fast feedback on Python files. Use `make check` before pushing to ensure CI will pass.

## Pull Request Process 🔄

### 1. Fork and Clone

```bash
# Fork via GitHub UI, then:
git clone git@github.com:YOUR_USERNAME/nectar-sdk.git
cd nectar-sdk
git remote add upstream git@github.com:Black-Bee-Drones/nectar-sdk.git
```

### 2. Create Feature Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/bug-description
```

**Branch Naming**:
- `feat/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Test additions/fixes

### 3. Make Changes

Follow the project code style:

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/)
- **Docstrings**: Use [NumPy style](https://numpydoc.readthedocs.io/en/latest/format.html)
- **Type hints**: Include type annotations for public APIs

### 4. Commit with Conventional Commits

We follow [Conventional Commits](https://www.conventionalcommits.org):

```bash
# Format: type(scope): description

git commit -m "feat(control): add obstacle avoidance strategy"
git commit -m "fix(vision): resolve camera initialization race condition"
git commit -m "docs(readme): update installation instructions"
```

**Types**:
| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `style` | Formatting (no code change) |
| `refactor` | Code restructuring |
| `test` | Test additions |
| `chore` | Build/tooling |

### 5. Push and Create PR

```bash
git push origin feat/your-feature-name
```

Then open a Pull Request via GitHub using our [PR template](../.github/PULL_REQUEST_TEMPLATE.md).

## Code Guidelines 📝

### Documentation

- Update module README.md when adding features
- Add docstrings to public classes and methods
- Include usage examples for new APIs

**README conventions** (gold standard: [`control/mavros/README.md`](../nectar/nectar/control/mavros/README.md)):

- **Structure**: Role/intro → one Mermaid diagram → tables (topics/services/params/args) → References. Keep prose tight and technical.
- **Single source of truth**: document shared logic once and link to it; do not restate the same thing in two READMEs. ArduPilot flight logic lives in [`ardupilot/README.md`](../nectar/nectar/control/ardupilot/README.md); indoor VSLAM in [`localization/README.md`](../nectar/nectar/control/localization/README.md); install in [`docs/INSTALL.md`](INSTALL.md); Docker in [`docker/README.md`](../docker/README.md); simulation in [`simulation/README.md`](../nectar/simulation/README.md). The root README and parent module READMEs link, they don't duplicate.
- **One diagram per README**: put the detailed class diagram in the module README; keep the root README's diagram high-level.
- **Stay grounded**: every command, flag, topic, and class name must match the code. Prefer real argparse flags / parameter names over invented ones.
- **When you add a module**: sync the root README (Features, Documentation table, directory tree) and the parent module's index, and add it to the Module Structure list below.

**Docstring Example**:
```python
def move_to(
    self,
    x: float,
    y: float,
    z: float,
    precision: float = 0.2,
) -> bool:
    """
    Navigate to a position in the world frame.

    Parameters
    ----------
    x : float
        Target X position in meters.
    y : float
        Target Y position in meters.
    z : float
        Target Z position (altitude) in meters.
    precision : float, optional
        Position tolerance in meters. Default is 0.2.

    Returns
    -------
    bool
        True if target reached within timeout, False otherwise.

    Examples
    --------
    >>> drone.move_to(x=2.0, y=1.0, z=1.5, precision=0.3)
    True
    """
```

### Testing

- Ensure existing tests pass before submitting
- Add tests for new functionality when possible
- Test with actual hardware when modifying drone control code

### Module Structure

When adding new components:

1. **Control Module**: extend `BaseDrone` or implement the `Drone` protocol; register in `DroneFactory`. Transport-agnostic ArduPilot logic belongs in `control/ardupilot/`; indoor external-nav (VSLAM, vision-pose bridge) in `control/localization/`.
2. **Vision Module**:
   - Cameras: add to `vision/camera/drivers/`, register in `CameraFactory`
   - Algorithms: add to `vision/algorithms/<category>/`
3. **AI Module**: extend `BaseDetectionModel` (or the segmentation equivalent), register in `Detector`/`Segmentor`
4. **ROS entry points**: nodes go in the relevant `nodes/` directory and `launch/` files in `nectar/launch/`; install both in `nectar/CMakeLists.txt`
5. **Export**: add public symbols to `__init__.py` (heavy deps via `_LAZY_ATTRS`)
6. **Document**: update the module README.md and sync the root README index/tree

### Import-time Contract

Heavy third-party dependencies (`torch`, `transformers`, `rfdetr`, `tensorflow`, `jax`, `matplotlib`, `mediapipe`, `pyrealsense2`, `depthai`, `supervision`, `ultralytics`, `pandas`, `geopy`) **must not** be imported at module load time on the path of `from nectar.ai import Detector`, `from nectar.vision import ImageHandler`, or `from nectar.control import MavrosConfig`.

Two patterns are used to enforce this, both standard ([PEP 562](https://peps.python.org/pep-0562/), the same approach as scikit-learn / NumPy / SciPy):

1. **Lazy package surface in `__init__.py`**: heavy re-exports go through a `_LAZY_ATTRS` dict and `__getattr__`. Lightweight types (dataclasses, enums, exceptions) stay eager. See `nectar/ai/detection/__init__.py` and `nectar/vision/__init__.py` for the canonical pattern.
2. **Local imports in functions**: when a module needs `matplotlib` / `pandas` only inside a plotting helper, the import lives inside the function body, not at the top of the file. See `nectar/vision/algorithms/distance/calibrator.py::ModelCalibrator.plot`.

Verify the contract by spawning a fresh interpreter and asserting the forbidden modules are absent from `sys.modules` after a public import:

```bash
python -c "import sys, nectar.control; assert 'torch' not in sys.modules and 'mediapipe' not in sys.modules"
```

If you add a new heavy dependency or re-export, route it through `_LAZY_ATTRS` (or a function-local import) so the public import path stays light.

## Review Process 👀

After submission:

1. Maintainers review code and provide feedback
2. Address requested changes
3. Once approved, PR is merged

Be patient and responsive to feedback. Thank you for contributing!

## Questions?

- [GitHub Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) for general questions
- [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues) for bugs/features
