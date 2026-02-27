"""
TensorBoard server management utilities.
"""

import atexit
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TensorBoardManager:
    """
    Manages TensorBoard server lifecycle.

    Handles starting and stopping TensorBoard server processes with proper
    cleanup and error handling.

    Examples
    --------
    >>> manager = TensorBoardManager()
    >>> manager.start_server(log_dir="outputs", port=6006)
    >>> # ... training ...
    >>> manager.stop_server()
    """

    def __init__(self):
        """Initialize TensorBoard manager."""
        self.process: Optional[subprocess.Popen] = None
        self.logger = logging.getLogger(__name__)
        self._cleanup_registered = False

    def start_server(self, log_dir: str, port: int = 6006, is_main_process: bool = True) -> None:
        """
        Start TensorBoard server in the background.

        Parameters
        ----------
        log_dir : str
            Directory containing TensorBoard logs.
        port : int, optional
            Port to run TensorBoard on. Defaults to 6006.
        is_main_process : bool, optional
            Only start server if this is the main process. Defaults to True.

        Notes
        -----
        The server process is automatically cleaned up on exit via atexit.
        """
        if not is_main_process:
            self.logger.info("Not the main process, skipping TensorBoard server start")
            return

        if self.process is not None:
            if self.process.poll() is None:
                self.logger.warning("TensorBoard server is already running")
                return
            self.process = None

        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            log_file = log_path / "tensorboard_server.log"

            self.logger.info(f"Starting TensorBoard server on port {port}, logs at {log_dir}")

            log_fd = open(log_file, "w")

            self.process = subprocess.Popen(
                [
                    "tensorboard",
                    "--logdir",
                    str(log_path),
                    "--port",
                    str(port),
                    "--bind_all",
                ],
                stdout=log_fd,
                stderr=log_fd,
                preexec_fn=os.setsid,  # Create a new process group
            )

            if not self._cleanup_registered:
                atexit.register(self.stop_server)
                self._cleanup_registered = True

            time.sleep(2)

            if self.process.poll() is None:
                self.logger.info(f"TensorBoard server started at http://localhost:{port}")
            else:
                self.logger.error("TensorBoard server failed to start")
                self.process = None

        except Exception as e:
            self.logger.error(f"Failed to start TensorBoard server: {e}")
            self.process = None

    def stop_server(self) -> None:
        """
        Stop TensorBoard server if it's running.

        Notes
        -----
        This method is safe to call multiple times and when the server
        is not running.
        """
        if self.process is not None:
            try:
                # Kill the entire process group
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
                self.process.wait(timeout=5)
                self.logger.info("TensorBoard server stopped")
            except ProcessLookupError:
                # Process already terminated
                pass
            except Exception as e:
                self.logger.error(f"Error stopping TensorBoard server: {e}")
            finally:
                self.process = None
