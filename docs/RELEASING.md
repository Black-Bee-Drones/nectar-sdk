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
- `v0.2.0 "Tadini"` — team captain
- `v1.0.0 "CBR 2026"` — competition name
- `v1.1.0 "Mangalarga"` — internal code name

## Release Checklist

### 1. Version bump PR

Create a PR that updates the version:

- `mirela_sdk/pyproject.toml` → `version = "X.Y.Z"`
- `CITATION.cff` → `version: X.Y.Z` and `date-released`

CI runs `code-quality` (lint) and `pr-check` (Humble build + verify) on the PR.

### 2. Merge to main

After review, merge the PR. CI runs `build-test` (all distros: Humble, Jazzy, Kilted).

Check the [Actions tab](https://github.com/Black-Bee-Drones/mirela-sdk/actions) — all green before proceeding.

### 3. Create GitHub release

- Go to [Releases](https://github.com/Black-Bee-Drones/mirela-sdk/releases/new)
- Tag: `vX.Y.Z` (create new tag, targeting `main`)
- Title: `vX.Y.Z "Code Name"`
- Click "Generate release notes" for the changelog
- Publish

### 4. CI automatically

`docker-push.yml` triggers and for each distro (Humble, Jazzy, Kilted):

1. Builds the Docker image with RealSense
2. Runs `verify` + `realsense-verify`
3. **Only if all checks pass**: pushes to Docker Hub

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

| Workflow | Trigger | Distros | What it does |
|---|---|---|---|
| `code-quality.yml` | PR + push to main | — | Lint + format (~30s) |
| `pr-check.yml` | PR to main | Humble | Build Docker + verify (catches regressions before merge) |
| `build-test.yml` | Push to main, weekly | All 3 | Build Docker + verify (full coverage) |
| `docker-push.yml` | GitHub release | All 3 | Build → verify → push to Docker Hub |

The build and verify logic is shared via `_build-verify.yml` (reusable workflow).
