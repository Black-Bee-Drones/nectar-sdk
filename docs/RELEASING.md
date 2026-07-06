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

- `nectar/pyproject.toml` → `version = "X.Y.Z"`
- `nectar/package.xml` → `<version>X.Y.Z</version>`
- `CITATION.cff` → `version: X.Y.Z` and `date-released`

CI runs `code-quality` (lint) and `pr-check` (Humble Docker build + `verify` + `verify-functional`) on the PR.

### 2. Merge to main

After review, merge the PR. CI runs on push to `main`:

- `build-test-{humble,jazzy,kilted}` — Docker build + `verify` + `verify-functional` (+ RealSense where enabled; Humble also on amd64 and arm64)
- `docs.yml` — builds and deploys the documentation site to GitHub Pages

Check the [Actions tab](https://github.com/Black-Bee-Drones/nectar-sdk/actions) — all green before proceeding.

### 3. Create GitHub release

- Go to [Releases](https://github.com/Black-Bee-Drones/nectar-sdk/releases/new)
- Tag: `vX.Y.Z` (create new tag, targeting `main`)
- Title: `vX.Y.Z "Code Name"`
- Include breaking-change migration notes when applicable (see the merge PR description)
- Click "Generate release notes" for the changelog, then publish

### 4. CI automatically

`docker-push.yml` triggers on release publish. For each distro (Humble, Jazzy, Kilted) and architecture (amd64, arm64):

1. Builds the Docker image with RealSense and drone drivers (`mavros`, `crazyflie`)
2. Runs `verify` + `verify-functional` + `realsense-verify`
3. **Only if all checks pass**: pushes multi-arch manifests to Docker Hub

## Documentation site (GitHub Pages)

- **URL:** [black-bee-drones.github.io/nectar-sdk](https://black-bee-drones.github.io/nectar-sdk/)
- **Source:** `website/` (authored pages), `docs/`, and module READMEs assembled by `scripts/docs/sync_readmes.py`
- **Workflow:** `.github/workflows/docs.yml` — build on PR; build + deploy on push to `main`
- **Repo setting (one-time):** Settings → Pages → Build and deployment → **GitHub Actions**
- **Local preview:** `make docs-install && make docs-serve`

## Docker Hub

Images are pushed to [Docker Hub](https://hub.docker.com/r/blackbeedrones/nectar-sdk) on every release.

| Tag pattern | Example | Contents |
|---|---|---|
| `:<distro>` | `humble`, `jazzy`, `kilted` | Latest release for that distro |
| `:<distro>-vX.Y.Z` | `humble-v1.1.0` | Specific release |

Pull and run:

```bash
docker pull blackbeedrones/nectar-sdk:humble
docker run -it --rm --net=host blackbeedrones/nectar-sdk:humble
```

## CI Workflows

| Workflow | Trigger | Distros | What it does |
|---|---|---|---|
| `code-quality.yml` | PR to `main` or `dev` | — | Lint + format (~30s) |
| `pr-check.yml` | PR to `main` | Humble (amd64) | Docker build + `verify` + `verify-functional` |
| `build-test-humble.yml` | Push to `main`, weekly (Mon 05:00 UTC) | Humble (amd64 + arm64) | Docker build + `verify` + `verify-functional` + RealSense |
| `build-test-jazzy.yml` | Push to `main`, weekly (Mon 05:00 UTC) | Jazzy | Docker build + `verify` + `verify-functional` + RealSense |
| `build-test-kilted.yml` | Push to `main`, weekly (Mon 05:00 UTC) | Kilted | Docker build + `verify` + `verify-functional` + RealSense |
| `docs.yml` | PR (build) / push to `main` (build + deploy) | — | Zensical site; deploys to GitHub Pages |
| `docker-push.yml` | GitHub release | All 3 × amd64 + arm64 | Build → `verify` + `verify-functional` + RealSense → push to Docker Hub |

The Docker build and verify logic is shared via `_build-verify.yml` (reusable workflow). `docker-push.yml` mirrors the same verification steps before publishing release images.
