#!/usr/bin/env python3
"""Assemble Portuguese docs into build/docs-pt/ and emit the sibling path map."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
I18N_PT = REPO / "i18n" / "pt"
WEBSITE = REPO / "website"
DOCS_EN = REPO / "build" / "docs"
DOCS_PT = REPO / "build" / "docs-pt"

# Shared static dirs from website/ (same assets/CSS/JS as the English site).
SHARED_DIRS = ("assets", "stylesheets", "javascripts", "includes")

SITE_BASE = "/nectar-sdk"


def page_path(md_rel: str) -> str:
    """MkDocs URL path for a markdown file relative to the docs root (no leading slash)."""
    if md_rel.endswith("/index.md"):
        return md_rel[: -len("/index.md")]
    if md_rel == "index.md":
        return ""
    if md_rel.endswith(".md"):
        return md_rel[: -len(".md")]
    return md_rel


def collect_pt_pages() -> list[str]:
    pages: list[str] = []
    if not I18N_PT.is_dir():
        return pages
    for path in sorted(I18N_PT.rglob("*.md")):
        rel = path.relative_to(I18N_PT).as_posix()
        pages.append(page_path(rel))
    return pages


def write_paths_json(docs_dir: Path, pages: list[str]) -> None:
    js_dir = docs_dir / "javascripts"
    js_dir.mkdir(parents=True, exist_ok=True)
    payload = {"base": SITE_BASE, "paths": pages}
    (js_dir / "i18n-paths.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    if not I18N_PT.is_dir():
        raise SystemExit(f"missing Portuguese sources: {I18N_PT}")

    DOCS_PT.parent.mkdir(parents=True, exist_ok=True)
    if DOCS_PT.exists():
        shutil.rmtree(DOCS_PT)
    DOCS_PT.mkdir(parents=True)

    for name in SHARED_DIRS:
        src = WEBSITE / name
        if src.is_dir():
            shutil.copytree(src, DOCS_PT / name)

    n_files = 0
    for path in I18N_PT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(I18N_PT)
        dest = DOCS_PT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        n_files += 1

    pages = collect_pt_pages()
    write_paths_json(DOCS_PT, pages)
    if DOCS_EN.is_dir():
        write_paths_json(DOCS_EN, pages)
    else:
        print(
            "  ! English build/docs missing — run sync_readmes.py first for EN path map"
        )

    rel = DOCS_PT.relative_to(REPO).as_posix()
    print(
        f"assembled {n_files} Portuguese file(s) into {rel}/ "
        f"({len(pages)} page path(s) for language switcher)"
    )


if __name__ == "__main__":
    main()
