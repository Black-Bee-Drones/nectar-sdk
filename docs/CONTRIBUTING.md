# Contributing to Nectar SDK

Discuss significant changes via [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues)
or [Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) before implementing,
and read the [Code of Conduct](CODE_OF_CONDUCT.md) first.

## Issues and Feature Requests

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

### Python environment

The SDK installs Python dependencies with [uv](https://github.com/astral-sh/uv) into a shared workspace venv (`$WORKSPACE/.venv`) that every package in the workspace reuses. See the [installation guide](setup/index.md#python-environment).

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

## Pull Request Process

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

## Code Guidelines

### Documentation

- Update module README.md when adding features
- Add docstrings to public classes and methods
- Include usage examples for new APIs

**README conventions** (gold standard: [`control/mavros/README.md`](../nectar/nectar/control/mavros/README.md)):

- **Structure (progressive disclosure)**: lead with a one-line purpose, then an **At a glance** runnable snippet (the common case), then **Concepts** (short prose + one mid-level diagram), then task-oriented **Usage**, then a **Reference** section for exhaustive tables (topics/services/params/types). Usage comes before the detailed class diagram, never after a wall of it. Keep prose tight and technical — no buzzwords, no repetition.
- **Single source of truth**: document shared logic once and link to it; do not restate the same thing in two READMEs. shared flight logic lives in [Vehicle core](../nectar/nectar/control/vehicle/README.md) (ArduPilot specifics in [ArduPilot](../nectar/nectar/control/ardupilot/README.md)); indoor VSLAM in [Localization](../nectar/nectar/control/localization/README.md); install in [Setup guide](setup/index.md); Docker in [Docker guide](../docker/README.md); simulation in [Simulation](../nectar/simulation/README.md). The root README and parent module READMEs link, they don't duplicate.
- **Diagrams (Mermaid, rendered natively by Zensical)**: keep one diagram per README, in a **Concepts** section *after* the at-a-glance usage (never the first thing on the page). Zensical renders Mermaid client-side and adapts fonts/colors to the active light/dark scheme, and every diagram is click-to-zoom/pan (see `website/javascripts/`). For the **technical** diagrams (class, sequence, state) rely on the theme — do **not** set colors, so they stay legible in both schemes. Reserve colors for the high-level **architecture/overview** diagram, where a curated `classDef` palette (mid-tone `fill:` with an explicit text `color:`) aids comprehension and reads on both schemes. Use the **ELK** layout (`config: { layout: elk }` in the diagram frontmatter) only for dense flowcharts on the **site** — GitHub's Mermaid has no ELK, so never put `layout: elk` in a README that must also render on GitHub. Avoid wrapping Mermaid in `<details>`/collapsibles (the fence does not render inside raw-HTML blocks). Git graphs render but are unthemed and weak on mobile — use sparingly.
- **Renders in the strict parser**: the docs site uses Python-Markdown, which is stricter than GitHub. Put a blank line before every list, table, and fenced code block (rules `MD022`/`MD031`/`MD032`/`MD058`, enforced by `markdownlint-cli2` in pre-commit and CI). Markdown that passes the linter renders on both the site and GitHub; the reverse is not guaranteed. Preview locally with `make docs-serve`.
- **Tabs and admonitions are site-only**: content tabs (`=== "..."`) and `!!!`/`???` admonitions render only on the docs site, not on GitHub. Use them on the authored `website/` pages and the site-first guides under `docs/` (setup, Docker), where they carry the reader's choice (backend, camera, OS) end to end. Module and example READMEs are shown on GitHub too, so there present alternatives as separate **bold-labeled fenced blocks** (not tabs) and use plain blockquotes (`> **Warning:** ...`) for notes. A fence that uses `#` comments as case/variant headers should become bold-labeled blocks (or a table) in a README, and a tab group on a site page.
- **Human link text**: never use a path as the visible link text (`[vehicle/README.md](...)`, `[control/px4/config](...)`). Write a human title (`[Vehicle core](...)`, `[PX4 config](...)`). Inline source-file pointers (`([`sequencer.py`](sequencer.py))`) are fine. Symbol → generated-API links belong on `website/` pages only (a README link to `api/*.md` is not dual-render-safe).
- **Stay grounded**: every command, flag, topic, and class name must match the code. Prefer real argparse flags / parameter names over invented ones.
- **When you add a module**: sync the root README (Features, Documentation table, directory tree) and the parent module's index, and follow [Adding a component](#adding-a-component) below.

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

The functional suite lives in [`nectar/test/`](../nectar/test) (it is **not**
installed with the package) and is plain `pytest`:

- `nectar/test/functional/` — one `test_<module>.py` per SDK module. Each test
  performs a *real operation* on synthetic inputs or a loopback. Tests
  self-skip (never fail) when an optional dependency is absent, via
  `pytest.importorskip(...)`.
- `nectar/test/hardware/` — device-gated checks (RealSense, OAK-D, TF-Luna),
  marked `hardware` and **deselected by default**.
- `nectar/test/conftest.py` + `nectar/test/helpers.py` — fixtures (`ros_node`,
  `fake_fcu`, `qt_app`) and the loopback FCU.

Run it:

```bash
make verify-functional                      # all modules (hardware/gpu deselected)
make verify-functional MODULE="vision control"   # subset -> pytest -m "vision or control"
make test                                   # colcon test: the suite + cmake/xml lint
make verify-hardware                         # opt in to device checks on the rig
# (equivalently, from the package dir: cd nectar && pytest test/hardware -m hardware)
```

Guidelines:

- **Add a test for new functionality.** Put it in the matching
  `test/functional/test_<module>.py`, tag the module with `pytestmark =
  pytest.mark.<module>`, and gate anything that needs a device/GPU/sim/network
  with the `hardware` / `gpu` / `sim` / `network` markers (registered in
  `pyproject.toml`). Assert with plain `assert`; skip with `pytest.skip(...)` /
  `pytest.importorskip(...)` — never fail for a missing optional dependency.
- **Lint/format with ruff** (the single source of truth — `make lint` /
  `make format`, also enforced by pre-commit). `make verify-functional` self-skips
  cleanly, so a green run on your machine reflects what your install can actually do.
- **Test with actual hardware** when modifying drone control code, and run the
  relevant `make verify-functional` markers before submitting.
- `make doctor` prints a read-only report of the current environment and devices —
  handy when a test skips and you want to know why.

#### Local CI (cross-distro)

The checks run at increasing fidelity:

- **Lint** — `make check` (ruff via pre-commit).
- **Host suite** (richest; all installed deps incl. AI/Qt/CUDA) — `make verify`,
  `make verify-functional`, `make verify-hardware` on your dev machine.
- **Cross-distro in Docker** — `make ci-local` builds the SDK image from the
  *local* source for each ROS distro and runs `verify` + `verify-functional` in
  each, mirroring [`.github/workflows/_build-verify.yml`](../.github/workflows/_build-verify.yml).
  It prints one pass/fail summary and writes a JUnit report per distro to
  `ci-local-results/`. amd64 only (arm64 is covered on a Jetson; Windows via WSL2
  later). It builds one image at a time and removes it afterwards to bound disk.

  ```bash
  make ci-local                                  # humble jazzy kilted (sdk stage)
  make ci-local DISTROS=jazzy                     # one distro
  make ci-local DISTROS="humble kilted" FULL=1    # include torch/AI (sdk-full; heavy)
  make ci-local REALSENSE=1                        # also build librealsense + realsense-verify
  ```

  Disk: full image builds are large. Docker's data-root must have several GB free
  (each `sdk` image is ~4-5 GB, `sdk-full` ~10 GB); the runner aborts a build below
  `MIN_FREE_GB` (default 8). Reclaim with `docker system prune` / remove old images.

#### SITL / integration flights (Tier 3)

The suite in [`nectar/test/sitl/`](../nectar/test/sitl) flies a real smoke mission
in a **headless** simulator for each firmware + protocol (connect -> takeoff ->
move -> land), validating the vehicle core and the firmware/protocol link
end to end. The `sim_session` fixture owns the sim lifecycle (reusing
`make sim-start` / `sim-bridge` / `sim-stop`), so a single command replaces the
manual two-terminal orchestration.

```bash
make verify-sitl                          # full matrix (needs the sim stack: make sim-install)
make verify-sitl FIRMWARE=px4 PROTOCOL=dds  # one entry (FIRMWARE -> marker, PROTOCOL -> -k)
```

Matrix: `ardupilot` (mavros, mavlink), `px4` (mavros, mavlink, dds), `crazyflie`
(Crazyswarm2 sim). Bebop is hardware-only (no simulator). The tier is marked
`sitl` and **deselected by default**.

Run it where the sim stack is installed (`make sim-install`): your dev machine or
the Jetson, and as a pre-release gate. It is **not** in CI — building the
simulators (ArduPilot + PX4 + Gazebo, all from source) takes ~45-70 min and there
is no apt binary to shortcut it, so it is not worth a per-PR or scheduled job. The
same `make verify-sitl` command runs unchanged on amd64 and arm64. (Crazyflie
self-skips unless the Crazyswarm2 `crazyflie_sim` backend is built from source.)

To add a firmware/protocol: add a `SimSpec` to
[`nectar/test/sitl/sim_helpers.py`](../nectar/test/sitl/sim_helpers.py) (its
`start_cmds`, drone type, config preset, and flight envelope); the parametrized
`test_smoke_flight` and the markers pick it up automatically. The deeper
ArduPilot navigation suite stays in
[`examples/simulation/sitl_test.py`](../nectar/nectar/examples/simulation/sitl_test.py).

### Adding a component

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

## Review Process

Maintainers review the code and provide feedback; address the requested changes and, once
approved, the PR is merged.

## Questions?

- [GitHub Discussions](https://github.com/Black-Bee-Drones/nectar-sdk/discussions) for general questions
- [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues) for bugs/features
