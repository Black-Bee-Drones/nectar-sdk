# Contributing to Mirela SDK 🐝

Thank you for your interest in contributing! This guide will help you get started.

## Before You Start

Please discuss significant changes via [GitHub Issues](https://github.com/Black-Bee-Drones/mirela-sdk/issues) or [Discussions](https://github.com/Black-Bee-Drones/mirela-sdk/discussions) before implementation.

Read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

## Issues and Feature Requests 🐛

### Reporting Bugs

Create bug reports that are:

- **Reproducible**: Include steps to reproduce the issue
- **Specific**: Version numbers, OS, hardware details
- **Unique**: Search existing issues first
- **Scoped**: One bug per report

### Feature Requests

Check [Discussions](https://github.com/Black-Bee-Drones/mirela-sdk/discussions) for ongoing conversations before opening a new request.

## Development Setup

Install [pre-commit](https://pre-commit.com/) hooks (one-time setup):

```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on `git commit`. To check all files manually:

```bash
pre-commit run --all-files
```

You can also run linting and formatting directly via Make:

```bash
make lint        # check for issues
make lint-fix    # auto-fix safe issues
make format      # format all code
```

## Pull Request Process 🔄

### 1. Fork and Clone

```bash
# Fork via GitHub UI, then:
git clone git@github.com:YOUR_USERNAME/mirela-sdk.git
cd mirela-sdk
git remote add upstream git@github.com:Black-Bee-Drones/mirela-sdk.git
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

1. **Control Module**: Extend `BaseDrone` or implement `Drone` protocol
2. **Vision Module**: 
   - Cameras: Add to `camera/drivers/`, register in `CameraFactory`
   - Algorithms: Add to `algorithms/<category>/`
3. **AI Module**: Extend `BaseDetectionModel`, register in `Detector`
4. **Export**: Add public symbols to `__init__.py`
5. **Document**: Update module README.md

## Review Process 👀

After submission:

1. Maintainers review code and provide feedback
2. Address requested changes
3. Once approved, PR is merged

Be patient and responsive to feedback. Thank you for contributing!

## Questions?

- [GitHub Discussions](https://github.com/Black-Bee-Drones/mirela-sdk/discussions) for general questions
- [GitHub Issues](https://github.com/Black-Bee-Drones/mirela-sdk/issues) for bugs/features
