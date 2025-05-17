import os
import shlex
import subprocess
from time import sleep


class ProcessUtils:
    @staticmethod
    def is_gui_available() -> bool:
        """
        Check if the GUI is available
        """
        try:
            # Check if the DISPLAY environment variable is set
            return bool(
                subprocess.run(
                    ["which", "gnome-terminal"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ).returncode
                == 0
            )
        except Exception:
            print("\033[94mGUI is not available\033[94m")
            return False

    @staticmethod
    def start_process(
        command: str, name: str = "my_session", gui: bool = False
    ) -> bool:
        """
        Start a process with gnome-terminal if GUI is available,
        otherwise start it in a tmux session.

        :param command: The command to start the process
        :param name: The representation name of the process
        :param gui: Whether to use GUI (gnome-terminal) if available

        :return: True if the process started successfully, False otherwise
        """
        print(f"-- Starting process: {command}")

        if gui and ProcessUtils.is_gui_available():
            print("\033[94mGUI is available\033[0m")
            print(f"\033[94mInitializing {name} in a new terminal\033[0m")
            try:
                process = subprocess.Popen(
                    shlex.split(f"gnome-terminal -- {command}"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    print(
                        f"\033[91m-- Error starting {name} in GUI: {stderr.decode()}\033[0m"
                    )
                    return False
                else:
                    print(f"\033[92m-- Started {name} in GUI successfully\033[0m")
                    return True
            except Exception as e:
                print(f"\033[91m-- Exception starting {name} in GUI: {str(e)}\033[0m")
                return False
        else:
            # First kill any existing tmux session with this name
            ProcessUtils.kill_process(name)

            # Create a new tmux session
            print("\033[94mInitializing process in a tmux session\033[0m")
            print(
                f"\033[95mFor access session, use the command: tmux attach -t {name}\033[0m"
            )

            try:
                # Create the tmux session with the command
                process = subprocess.Popen(
                    shlex.split(f'tmux new-session -d -s {name} "{command}"'),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                stdout, stderr = process.communicate()

                # Give tmux a moment to start the session
                sleep(1.5)

                # Verify the session was actually created
                if not ProcessUtils.has_process(name):
                    print(f"\033[91m-- Failed to create tmux session {name}\033[0m")
                    if stderr:
                        print(f"\033[91m-- Error: {stderr.decode()}\033[0m")
                    return False

                # Check process return code
                if process.returncode != 0:
                    print(f"\033[91m-- Error starting {name}: {stderr.decode()}\033[0m")
                    return False
                else:
                    print(f"\033[92m-- Started {name} successfully\033[0m")
                    return True

            except Exception as e:
                print(f"\033[91m-- Exception starting {name}: {str(e)}\033[0m")
                return False

    @staticmethod
    def has_process(name: str = "my_session") -> bool:
        """
        Check if a process started in a tmux session exists

        :param name: The name of the tmux session
        """
        print(f"-- Checking process: {name}")

        # Check if the tmux session exists
        check_session = subprocess.Popen(
            shlex.split(f"tmux has-session -t {name}"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = check_session.communicate()

        if check_session.returncode == 0:
            print(f"\033[93m-- Session {name} exists.\033[0m")
            return True
        else:
            print(f"\033[91m-- Session {name} does not exist.\033[0m")
            return False

    @staticmethod
    def kill_process(name: str = "my_session") -> bool:
        """
        Kill a process started in a tmux session

        :param name: The name of the tmux session
        """
        print(f"-- Killing process: {name}")

        # Check if the tmux session exists
        if ProcessUtils.has_process(name):
            print(f"\033[93mKilling session {name}\033[0m")
            process = subprocess.Popen(
                shlex.split(f"tmux kill-session -t {name}"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = process.communicate()

            if process.returncode != 0:
                print(f"\033[91m-- Error killing {name}: {process.returncode}\033[0m")
                return False
            else:
                print(f"\033[92m-- Killed {name} successfully\033[0m")
                return True
        else:
            print(f"\033[91m-- Session {name} does not exist.\033[0m")
            return True
