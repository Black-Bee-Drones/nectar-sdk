from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Optional

logger = logging.getLogger(__name__)

BY_ID_DIR = Path("/dev/v4l/by-id")
BY_PATH_DIR = Path("/dev/v4l/by-path")


@dataclass(frozen=True)
class V4L2Link:
    """A ``/dev/v4l/by-id`` or ``by-path`` symlink and the node it points at."""

    name: str
    node: str


@dataclass(frozen=True)
class V4L2Device:
    """One camera block from ``v4l2-ctl --list-devices``."""

    name: str
    nodes: tuple[str, ...]
    by_id: tuple[V4L2Link, ...] = ()
    by_path: tuple[V4L2Link, ...] = ()


def list_v4l2_devices(
    *,
    listing: Optional[str] = None,
    by_id_dir: Optional[Path] = None,
    by_path_dir: Optional[Path] = None,
) -> list[V4L2Device]:
    """
    List V4L2 cameras and the by-id / by-path links that point at them.

    Parameters
    ----------
    listing : str, optional
        ``v4l2-ctl --list-devices`` text. When omitted, the command is run.
    by_id_dir, by_path_dir : Path, optional
        Symlink directories. Default to ``/dev/v4l/by-id`` and ``by-path``.
        A missing directory yields no links.

    Raises
    ------
    RuntimeError
        ``v4l2-ctl`` is missing, or it exits non-zero with no device text.
    """
    if listing is None:
        listing = _read_v4l2_listing()
    devices = _parse_list_devices(listing)
    return _attach_symlinks(
        devices,
        BY_ID_DIR if by_id_dir is None else by_id_dir,
        BY_PATH_DIR if by_path_dir is None else by_path_dir,
    )


def resolve_v4l2_device(query: str, devices: Optional[list[V4L2Device]] = None) -> str:
    """
    Return the ``/dev/videoN`` path for one camera.

    The query is a case-insensitive substring of the ``v4l2-ctl`` header or of a
    by-id / by-path link name. ``video-index0`` and ``video-index1`` of the same
    camera count as one camera. Zero matches, or more than one camera, raises.
    One camera opens the first ``/dev/videoN`` in its block, unless the query
    matches exactly one symlink: then that symlink's node is used.

    Parameters
    ----------
    query : str
        Product name, serial, or USB path fragment.
    devices : list of V4L2Device, optional
        Listing to search. When omitted, ``list_v4l2_devices()`` is called.

    Returns
    -------
    str
        Capture node, for example ``/dev/video0``.

    Raises
    ------
    RuntimeError
        The query is blank, matches nothing, or matches more than one camera.
        The message lists the devices that were found.
    """
    if devices is None:
        devices = list_v4l2_devices()
    needle = query.strip().casefold()
    if not needle:
        _fail("V4L2 device name is empty.")

    matches: list[tuple[V4L2Device, list[V4L2Link]]] = []
    for device in devices:
        links = _matching_links(device, needle)
        if needle in device.name.casefold() or links:
            matches.append((device, links))

    if len(matches) != 1:
        _fail(_miss_message(query, devices, len(matches)))

    device, links = matches[0]
    if len(links) == 1:
        return links[0].node
    return device.nodes[0]


def _read_v4l2_listing() -> str:
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError("v4l2-ctl --list-devices failed. Install v4l2-utils.") from exc
    stdout = result.stdout or ""
    if result.returncode != 0 and not stdout.strip():
        detail = (result.stderr or "").strip()
        message = "v4l2-ctl --list-devices failed"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(f"{message}. Install v4l2-utils.")
    return stdout


def _parse_list_devices(listing: str) -> list[V4L2Device]:
    """Parse ``v4l2-ctl --list-devices`` into camera blocks.

    A header line starts a camera. Tab-indented ``/dev/videoN`` lines are its
    nodes. ``/dev/mediaN`` lines are ignored. A header with no video node is dropped.
    """
    devices: list[V4L2Device] = []
    name: Optional[str] = None
    nodes: list[str] = []

    def flush() -> None:
        nonlocal name, nodes
        if name and nodes:
            devices.append(V4L2Device(name=name, nodes=tuple(nodes)))
        name = None
        nodes = []

    for line in listing.splitlines():
        if line.startswith("\t"):
            node = _video_node(line)
            if node and name is not None:
                nodes.append(node)
            continue
        if not line.strip():
            continue
        flush()
        name = line.strip()
        if name.endswith(":"):
            name = name[:-1].rstrip()
    flush()
    return devices


def _video_node(line: str) -> Optional[str]:
    marker = "/dev/video"
    start = line.find(marker)
    if start < 0:
        return None
    end = start + len(marker)
    while end < len(line) and line[end].isdigit():
        end += 1
    if end == start + len(marker):
        return None
    return line[start:end]


def _attach_symlinks(
    devices: list[V4L2Device],
    by_id_dir: Path,
    by_path_dir: Path,
) -> list[V4L2Device]:
    nodes = {node for device in devices for node in device.nodes}
    by_id = _links_for_nodes(by_id_dir, nodes)
    by_path = _links_for_nodes(by_path_dir, nodes)
    attached: list[V4L2Device] = []
    for device in devices:
        attached.append(
            V4L2Device(
                name=device.name,
                nodes=device.nodes,
                by_id=tuple(link for node in device.nodes for link in by_id.get(node, ())),
                by_path=tuple(link for node in device.nodes for link in by_path.get(node, ())),
            )
        )
    return attached


def _links_for_nodes(directory: Path, nodes: set[str]) -> dict[str, tuple[V4L2Link, ...]]:
    found: dict[str, list[V4L2Link]] = {node: [] for node in nodes}
    if not directory.is_dir():
        return {node: () for node in nodes}
    keys = {_node_key(node): node for node in nodes}
    for entry in sorted(directory.iterdir()):
        if not entry.is_symlink():
            continue
        try:
            key = _node_key(entry)
        except OSError:
            continue
        node = keys.get(key)
        if node is None:
            continue
        found[node].append(V4L2Link(name=entry.name, node=node))
    return {node: tuple(links) for node, links in found.items()}


def _node_key(path: str | Path) -> str:
    return os.path.realpath(path)


def _matching_links(device: V4L2Device, needle: str) -> list[V4L2Link]:
    return [link for link in (*device.by_id, *device.by_path) if needle in link.name.casefold()]


def _format_devices(devices: list[V4L2Device]) -> str:
    if not devices:
        return "(none)"
    lines: list[str] = []
    for device in devices:
        lines.append(f"{device.name}: {', '.join(device.nodes)}")
        for link in device.by_id:
            lines.append(f"  by-id: {link.name}")
        for link in device.by_path:
            lines.append(f"  by-path: {link.name}")
    return "\n".join(lines)


def _miss_message(query: str, devices: list[V4L2Device], count: int) -> str:
    listing = _format_devices(devices)
    if count == 0:
        return f"No V4L2 device matched {query!r}. Available:\n{listing}"
    return (
        f"{query!r} matched {count} V4L2 devices. Use a /dev/v4l/by-id or by-path name.\n{listing}"
    )


def _fail(message: str) -> NoReturn:
    logger.error("%s", message)
    raise RuntimeError(message)
