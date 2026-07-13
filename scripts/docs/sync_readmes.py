#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "website"  # authored, git-tracked
DOCS = REPO / "build" / "docs"  # assembled docs_dir, git-ignored (do not edit)
ASSETS_OUT = "assets/_generated"  # under DOCS
GH_BLOB = "https://github.com/Black-Bee-Drones/nectar-sdk/blob/main"
GH_TREE = "https://github.com/Black-Bee-Drones/nectar-sdk/tree/main"

# Mermaid diagrams are rendered natively by Zensical (client-side, theme-aware), so the
# ```mermaid fences pass through unchanged — no pre-rendering here.

# source (relative to repo root) -> output (relative to the assembled docs dir)
MANIFEST: dict[str, str] = {
    # Setup (split installation guide)
    "docs/setup/index.md": "setup/index.md",
    "docs/setup/drivers.md": "setup/drivers.md",
    "docs/setup/simulation.md": "setup/simulation.md",
    "docs/setup/realsense.md": "setup/realsense.md",
    "docs/setup/configuration.md": "setup/configuration.md",
    "docs/COMPATIBILITY.md": "setup/compatibility.md",
    "docker/README.md": "setup/docker.md",
    # Development
    "docs/development/commands.md": "development/commands.md",
    # Project docs
    "docs/CONTRIBUTING.md": "project/contributing.md",
    "docs/RELEASING.md": "project/releasing.md",
    "docs/SECURITY.md": "project/security.md",
    "docs/CODE_OF_CONDUCT.md": "project/code-of-conduct.md",
    # Control
    "nectar/nectar/control/README.md": "modules/control/index.md",
    "nectar/nectar/control/vehicle/README.md": "modules/control/vehicle.md",
    "nectar/nectar/control/ardupilot/README.md": "modules/control/ardupilot.md",
    "nectar/nectar/control/px4/README.md": "modules/control/px4.md",
    "nectar/nectar/control/mavros/README.md": "modules/control/mavros.md",
    "nectar/nectar/control/mavlink/README.md": "modules/control/mavlink.md",
    "nectar/nectar/control/localization/README.md": "modules/control/localization.md",
    "nectar/nectar/control/obstacles/README.md": "modules/control/obstacles.md",
    "nectar/nectar/control/pid/README.md": "modules/control/pid.md",
    "nectar/nectar/control/bebop/README.md": "modules/control/bebop.md",
    "nectar/nectar/control/crazyflie/README.md": "modules/control/crazyflie.md",
    # Vision / AI / sensors / interface / utils
    "nectar/nectar/vision/README.md": "modules/vision/index.md",
    "nectar/nectar/vision/camera/README.md": "modules/vision/camera.md",
    "nectar/nectar/vision/algorithms/README.md": "modules/vision/algorithms.md",
    "nectar/nectar/vision/nodes/README.md": "modules/vision/nodes.md",
    "nectar/nectar/ai/README.md": "modules/ai/index.md",
    "nectar/nectar/ai/detection/README.md": "modules/ai/detection.md",
    "nectar/nectar/ai/segmentation/README.md": "modules/ai/segmentation.md",
    "nectar/nectar/ai/classification/README.md": "modules/ai/classification.md",
    "nectar/nectar/sensors/README.md": "modules/sensors.md",
    "nectar/nectar/interface/README.md": "modules/interface.md",
    "nectar/nectar/utils/README.md": "modules/utils.md",
    # Examples
    "nectar/nectar/examples/control/README.md": "modules/examples/control.md",
    "nectar/nectar/examples/vision/README.md": "modules/examples/vision.md",
    "nectar/nectar/examples/ai/README.md": "modules/examples/ai.md",
    "nectar/nectar/examples/sensors/README.md": "modules/examples/sensors.md",
    # Simulation / interfaces
    "nectar/simulation/README.md": "modules/simulation.md",
    "nectar_interfaces/README.md": "modules/interfaces.md",
}

LINK_RE = re.compile(r'(!?)\[([^\]]*)\]\(\s*(<[^>]+>|[^)\s]+)\s*(?:"[^"]*")?\)')


def relpath(target: Path, start_dir: Path) -> str:
    return os.path.relpath(target, start_dir).replace(os.sep, "/")


def split_anchor(url: str) -> tuple[str, str]:
    path, sep, frag = url.partition("#")
    return path, (sep + frag if sep else "")


def rewrite(src_rel: str, out_rel: str, text: str, copied: dict[str, Path]) -> str:
    src_dir = (REPO / src_rel).parent
    out_dir = (DOCS / out_rel).parent

    def repl(match: re.Match[str]) -> str:
        bang, label, raw = match.group(1), match.group(2), match.group(3)
        url = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
        if url.startswith(("http://", "https://", "mailto:", "//", "#")):
            return match.group(0)
        path_part, anchor = split_anchor(url)
        if not path_part:
            return match.group(0)
        target = (src_dir / path_part).resolve()
        try:
            rel_repo = target.relative_to(REPO).as_posix()
        except ValueError:
            return match.group(0)  # escapes the repo; leave as-is

        if bang == "!":  # image -> copy into the site and re-point
            if target.exists():
                dest = DOCS / ASSETS_OUT / rel_repo.replace("/", "__")
                if rel_repo not in copied:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, dest)
                    copied[rel_repo] = dest
                return f"![{label}]({relpath(dest, out_dir)})"
            return match.group(0)

        if rel_repo in MANIFEST:  # link to another included page
            dest = DOCS / MANIFEST[rel_repo]
            return f"[{label}]({relpath(dest, out_dir)}{anchor})"

        base = GH_TREE if target.is_dir() else GH_BLOB  # source file/dir -> GitHub
        return f"[{label}]({base}/{rel_repo}{anchor})"

    result = LINK_RE.sub(repl, text)
    # GitHub parses Markdown inside block HTML implicitly; Python-Markdown needs a
    # `markdown` attribute on the wrapper (md_in_html) for e.g. centered images.
    result = result.replace('<div align="center">', '<div align="center" markdown>')
    return result


def main() -> None:
    DOCS.parent.mkdir(parents=True, exist_ok=True)
    if DOCS.exists():
        shutil.rmtree(DOCS)
    shutil.copytree(SRC, DOCS)  # authored, hand-written pages

    copied: dict[str, Path] = {}
    banner = "<!-- AUTO-GENERATED from {src} by scripts/docs/sync_readmes.py — edit the source. -->\n\n"
    for src_rel, out_rel in MANIFEST.items():
        src = REPO / src_rel
        if not src.exists():
            print(f"  ! missing source: {src_rel}")
            continue
        out = DOCS / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        body = rewrite(src_rel, out_rel, src.read_text(encoding="utf-8"), copied)
        out.write_text(banner.format(src=src_rel) + body, encoding="utf-8")

    rel = DOCS.relative_to(REPO).as_posix()
    print(
        f"assembled {len(MANIFEST)} generated + authored pages into {rel}/ ({len(copied)} asset(s))"
    )


if __name__ == "__main__":
    main()
