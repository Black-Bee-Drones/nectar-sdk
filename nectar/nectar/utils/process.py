import logging
import shlex
import subprocess
import sys
from time import sleep
from typing import List

_logger = logging.getLogger("nectar.utils.process")

if not _logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


class ProcessUtils:
    """
    Utility class for process management using tmux or gnome-terminal.
    """

    @staticmethod
    def is_gui_available() -> bool:
        """
        Check if GUI terminal (gnome-terminal) is available.

        Returns
        -------
        bool
            True if gnome-terminal is available, False otherwise.
        """
        try:
            result = subprocess.run(
                ["which", "gnome-terminal"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2.0,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_ros2_nodes(timeout: float = 5.0) -> List[str]:
        """
        Get list of running ROS2 nodes.

        Parameters
        ----------
        timeout : float, default=5.0
            Maximum time to wait for ros2 node list command in seconds.

        Returns
        -------
        List[str]
            List of fully qualified node names. Empty list on error or timeout.
        """
        try:
            result = subprocess.run(
                shlex.split("ros2 node list"),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return []
        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

    @staticmethod
    def is_node_running(node_pattern: str, timeout: float = 5.0) -> bool:
        """
        Check if a ROS2 node matching pattern is running.

        Parameters
        ----------
        node_pattern : str
            Node name or pattern to search for (substring match).
        timeout : float, default=5.0
            Maximum time to wait for ros2 node list command in seconds.

        Returns
        -------
        bool
            True if a matching node is found, False otherwise.
        """
        nodes = ProcessUtils.get_ros2_nodes(timeout)
        return any(node_pattern in node for node in nodes)

    @staticmethod
    def wait_for_node(
        node_pattern: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """
        Wait for a ROS2 node to appear in the node graph.

        Parameters
        ----------
        node_pattern : str
            Node name or pattern to search for (substring match).
        timeout : float, default=10.0
            Maximum time to wait in seconds.
        poll_interval : float, default=0.5
            Time between status checks in seconds.

        Returns
        -------
        bool
            True if node appeared within timeout, False otherwise.
        """
        elapsed = 0.0
        while elapsed < timeout:
            if ProcessUtils.is_node_running(node_pattern, timeout=2.0):
                return True
            sleep(poll_interval)
            elapsed += poll_interval
        return False

    @staticmethod
    def start_process(command: str, name: str = "my_session", gui: bool = False) -> bool:
        """
        Start a process in a tmux session or gnome-terminal.

        If a tmux session with the same name exists, it is killed first.

        Parameters
        ----------
        command : str
            Command to execute.
        name : str, default="my_session"
            Session name for tmux or process identifier.
        gui : bool, default=False
            If True and gnome-terminal is available, use GUI terminal instead of tmux.

        Returns
        -------
        bool
            True if process started successfully, False otherwise.
        """
        _logger.info("Starting process: %s", name)

        if gui and ProcessUtils.is_gui_available():
            _logger.info("Initializing %s in gnome-terminal", name)
            try:
                process = subprocess.Popen(
                    shlex.split(f"gnome-terminal -- {command}"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                _, stderr = process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    _logger.error("Failed to start %s in GUI: %s", name, error_msg)
                    return False
                _logger.info("\033[32mStarted %s in GUI successfully\033[0m", name)
                return True
            except Exception as e:
                _logger.error("Exception starting %s in GUI: %s", name, e)
                return False

        if ProcessUtils._has_tmux_session(name):
            _logger.debug("Killing existing tmux session: %s", name)
            ProcessUtils._kill_tmux_session(name)

        _logger.info("Initializing %s in tmux session", name)
        _logger.debug("Access session with: tmux attach -t %s", name)

        try:
            process = subprocess.Popen(
                shlex.split(f'tmux new-session -d -s {name} "{command}"'),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = process.communicate()

            sleep(1.5)

            if not ProcessUtils._has_tmux_session(name):
                error_msg = stderr.decode() if stderr else "Unknown error"
                _logger.error("Failed to create tmux session %s: %s", name, error_msg)
                return False

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                _logger.error("Error starting %s: %s", name, error_msg)
                return False

            _logger.info("\033[32mStarted %s successfully\033[0m", name)
            return True

        except Exception as e:
            _logger.error("Exception starting %s: %s", name, e)
            return False

    @staticmethod
    def has_process(name: str = "my_session") -> bool:
        """
        Check if a tmux session exists.

        Parameters
        ----------
        name : str, default="my_session"
            Tmux session name.

        Returns
        -------
        bool
            True if session exists, False otherwise.
        """
        return ProcessUtils._has_tmux_session(name)

    @staticmethod
    def _has_tmux_session(name: str) -> bool:
        """
        Internal method to check tmux session existence without logging.

        Parameters
        ----------
        name : str
            Tmux session name.

        Returns
        -------
        bool
            True if session exists, False otherwise.
        """
        try:
            result = subprocess.run(
                shlex.split(f"tmux has-session -t {name}"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2.0,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def kill_process(name: str = "my_session") -> bool:
        """
        Kill a tmux session.

        Parameters
        ----------
        name : str, default="my_session"
            Tmux session name.

        Returns
        -------
        bool
            True if session was killed or did not exist, False on error.
        """
        if not ProcessUtils._has_tmux_session(name):
            _logger.debug("Session %s does not exist", name)
            return True

        _logger.info("Killing tmux session: %s", name)
        return ProcessUtils._kill_tmux_session(name)

    @staticmethod
    def _kill_tmux_session(name: str) -> bool:
        """
        Internal method to kill tmux session without logging.

        Parameters
        ----------
        name : str
            Tmux session name.

        Returns
        -------
        bool
            True if session was killed, False on error.
        """
        try:
            result = subprocess.run(
                shlex.split(f"tmux kill-session -t {name}"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5.0,
                check=False,
            )
            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                _logger.error("Error killing %s: %s", name, error_msg)
                return False
            _logger.info("\033[32mKilled session %s successfully\033[0m", name)
            return True
        except Exception as e:
            _logger.error("Exception killing %s: %s", name, e)
            return False
