"""SDK-wide ROS 2 executor lifecycle.

Each subsystem owns its ``Node`` and registers it here. A shared executor
runs on a background thread so blocking calls never starve callbacks.
``EventsExecutor`` is preferred when available (Jazzy+), with
``MultiThreadedExecutor`` as fallback (Humble).
"""

from __future__ import annotations

import atexit
import threading
import time
from typing import List, Optional

import rclpy
from rclpy.executors import Executor, MultiThreadedExecutor
from rclpy.node import Node

try:
    from rclpy.executors import EventsExecutor as _DefaultExecutor
except ImportError:
    _DefaultExecutor = MultiThreadedExecutor


class _Runtime:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor: Optional[Executor] = None
        self._thread: Optional[threading.Thread] = None
        self._owns_executor = False
        self._nodes: List[Node] = []

    def init(self, num_threads: Optional[int] = None) -> Executor:
        """Create and start the SDK executor. Idempotent.

        ``num_threads`` is forwarded only to ``MultiThreadedExecutor``;
        ``EventsExecutor`` takes no thread count. ``None`` falls back to
        ``multiprocessing.cpu_count()``.
        """
        with self._lock:
            if self._executor is not None:
                return self._executor
            if not rclpy.ok():
                rclpy.init()
            if _DefaultExecutor is MultiThreadedExecutor:
                self._executor = MultiThreadedExecutor(num_threads=num_threads)
            else:
                self._executor = _DefaultExecutor()
            self._thread = threading.Thread(
                target=self._executor.spin, name="nectar-spin", daemon=True
            )
            self._thread.start()
            self._owns_executor = True
            return self._executor

    def ensure_context(self) -> None:
        """Initialize the rclpy context if needed, without creating the executor."""
        with self._lock:
            if not rclpy.ok():
                rclpy.init()

    def use_executor(self, executor: Executor) -> None:
        with self._lock:
            if self._executor is not None and self._owns_executor:
                raise RuntimeError("nectar.runtime already owns an executor; call shutdown() first")
            self._executor = executor
            self._owns_executor = False

    def get_executor(self) -> Executor:
        if self._executor is None:
            self.init()
        return self._executor

    def add_node(self, node: Node) -> None:
        with self._lock:
            self.get_executor().add_node(node)
            self._nodes.append(node)

    def remove_node(self, node: Node) -> None:
        with self._lock:
            if self._executor is not None:
                try:
                    self._executor.remove_node(node)
                except Exception:
                    pass
            if node in self._nodes:
                self._nodes.remove(node)

    def shutdown(self) -> None:
        with self._lock:
            if self._executor is None:
                return
            for node in list(self._nodes):
                try:
                    self._executor.remove_node(node)
                    node.destroy_node()
                except Exception:
                    pass
            self._nodes.clear()
            if self._owns_executor:
                try:
                    self._executor.shutdown()
                except Exception:
                    pass
                if self._thread is not None:
                    self._thread.join(timeout=2.0)
            self._executor = None
            self._thread = None
            self._owns_executor = False

    def detach(self) -> None:
        """Release an externally-owned executor registration.

        For an external owner that manages its
        own spin thread and node lifecycle: drops the runtime's reference so a
        stopped executor is not retained. No-op when the runtime owns the
        executor (use :meth:`shutdown` instead). Does not destroy nodes.
        """
        with self._lock:
            if self._owns_executor:
                return
            self._executor = None
            self._nodes.clear()

    @property
    def is_initialized(self) -> bool:
        return self._executor is not None

    @property
    def owns_executor(self) -> bool:
        return self._owns_executor


_runtime = _Runtime()


def init(num_threads: Optional[int] = None) -> Executor:
    """Initialize the SDK runtime. Returns the shared executor."""
    return _runtime.init(num_threads)


def ensure_context() -> None:
    """Initialize the rclpy context if needed, without creating the executor."""
    _runtime.ensure_context()


def use_executor(executor: Executor) -> None:
    """Use an externally managed executor; the caller spins it."""
    _runtime.use_executor(executor)


def get_executor() -> Executor:
    """Return the active executor, lazily initializing if needed."""
    return _runtime.get_executor()


def add_node(node: Node) -> None:
    """Register a node with the active executor."""
    _runtime.add_node(node)


def remove_node(node: Node) -> None:
    """Unregister a node from the active executor."""
    _runtime.remove_node(node)


def shutdown() -> None:
    """Tear down all registered nodes and stop the SDK-owned executor."""
    _runtime.shutdown()


def detach() -> None:
    """Release an externally-managed executor registration (see ``_Runtime.detach``)."""
    _runtime.detach()


def is_initialized() -> bool:
    return _runtime.is_initialized


def owns_executor() -> bool:
    return _runtime.owns_executor


def spin() -> None:
    """Block the calling thread until SIGINT; callbacks keep firing in the background."""
    try:
        while rclpy.ok():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


atexit.register(shutdown)
