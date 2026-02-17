# Release Process

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

```
vMAJOR.MINOR.PATCH
```

- **Major**: breaking API changes
- **Minor**: new features, backward-compatible
- **Patch**: bug fixes

## Code Names (optional)

Releases can have a code name associated with the version. The git tag is always `vX.Y.Z` (machine-readable). The GitHub release title includes the code name (human-readable).

Examples:
- `v0.2.0 "Captain Ana"` — team captain 2025
- `v1.0.0 "CBR 2025"` — Brazilian Robotics Competition
- `v1.1.0 "Ouro Preto"` — competition city

## Release Checklist

### 1. Prepare the release branch

```bash
git checkout -b release/vX.Y.Z
```

Update version in:
- `mirela_sdk/pyproject.toml` → `version = "X.Y.Z"`
- `CITATION.cff` → `version: X.Y.Z` and `date-released`

```bash
git add -A
git commit -m "release: vX.Y.Z"
git push origin release/vX.Y.Z
```

### 2. Open a PR to main

- Title: `release: vX.Y.Z`
- CI runs `code-quality.yml` (lint check)
- Review and merge

### 3. Verify the build

After merging, `build-test.yml` runs automatically on `main`:
- Builds Docker images for Humble, Jazzy, Kilted (with RealSense)
- Runs `verify` and `realsense-verify` inside each image
- Check the [Actions tab](https://github.com/Black-Bee-Drones/mirela-sdk/actions) — all green before proceeding

### 4. Create GitHub release

- Go to [Releases](https://github.com/Black-Bee-Drones/mirela-sdk/releases/new)
- Tag: `vX.Y.Z` (targeting `main`)
- Title: `vX.Y.Z "Code Name"`
- Description: changelog since last release (use "Generate release notes")
- Publish

### 5. CI automatically

`docker-push.yml` triggers and for each distro (Humble, Jazzy, Kilted):
1. Builds the Docker image with RealSense
2. Runs `verify` + `realsense-verify` inside the image
3. **Only if verification passes**: pushes to Docker Hub

If any verification fails, the image is NOT pushed.

## Docker Hub

Images are pushed to [Docker Hub](https://hub.docker.com/r/blackbeedrones/mirela-sdk) on every release.

| Tag pattern | Example | Contents |
|---|---|---|
| `:<distro>` | `humble`, `jazzy`, `kilted` | Latest release for that distro |
| `:<distro>-vX.Y.Z` | `humble-v0.2.0` | Specific release |

Pull and run:
```bash
docker pull blackbeedrones/mirela-sdk:humble
docker run -it --rm --net=host blackbeedrones/mirela-sdk:humble
```

## CI Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `code-quality.yml` | PR and push to main | Lint + format check (fast, ~30s) |
| `build-test.yml` | Push to main, weekly | Builds Docker images per distro, runs `verify` + `realsense-verify` |
| `docker-push.yml` | GitHub release published | Build → verify → push to Docker Hub (verify gates push) |

