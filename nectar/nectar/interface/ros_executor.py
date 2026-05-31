import threading
from typing import Optional

import rclpy
from PySide6.QtCore import QObject, Signal
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from nectar import runtime as nectar_runtime


class ROSExecutor(QObject):
    """ROS 2 executor manager for the Qt GUI.

    Owns the GUI's main node and a :class:`MultiThreadedExecutor` running on a
    background thread. Registers the executor with :mod:`nectar.runtime` so any
    SDK subsystem (drone, image handler) created from within the GUI shares this
    executor instead of spawning its own spin thread.
    """

    status_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._node: Optional[Node] = None
        self._executor: Optional[MultiThreadedExecutor] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def node(self) -> Optional[Node]:
        return self._node

    @property
    def is_running(self) -> bool:
        return self._running and rclpy.ok()

    def start(self, node_name: str = "nectar_gui") -> bool:
        """Start ROS 2 context and executor in a background thread."""
        with self._lock:
            if self._running:
                return True

            try:
                if not rclpy.ok():
                    rclpy.init()

                self._node = Node(node_name)
                self._executor = MultiThreadedExecutor()
                self._executor.add_node(self._node)
                nectar_runtime.use_executor(self._executor)

                self._running = True
                self._thread = threading.Thread(target=self._spin, daemon=True)
                self._thread.start()

                self.status_changed.emit(True)
                return True

            except Exception as e:
                self.error_occurred.emit(f"Failed to start ROS2: {e}")
                return False

    def _spin(self) -> None:
        """Spin executor in background thread."""
        try:
            while self._running and rclpy.ok():
                self._executor.spin_once(timeout_sec=0.1)
        except Exception as e:
            self.error_occurred.emit(f"ROS2 executor error: {e}")
            self._running = False
            self.status_changed.emit(False)

    def stop(self) -> None:
        """Stop ROS2 executor and cleanup resources."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._executor and self._node:
            try:
                self._executor.remove_node(self._node)
            except Exception:
                # Node may already be removed or executor shutdown
                pass

        if self._node:
            try:
                self._node.destroy_node()
            except Exception:
                # Node may already be destroyed
                pass

        self._node = None
        self._executor = None
        self._thread = None
        self.status_changed.emit(False)

    def shutdown(self) -> None:
        """Complete shutdown of ROS2 context."""
        self.stop()
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            # Context may already be shutdown
            pass

    def __del__(self) -> None:
        self.shutdown()
