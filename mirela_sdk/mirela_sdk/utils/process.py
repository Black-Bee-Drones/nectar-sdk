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

        :return: True if the process started successfully, False otherwise
        """
        print(f"-- Starting process: {command}")
        if gui and ProcessUtils.is_gui_available():
            print("\033[94mGUI is available\033[0m")
            print(f"\033[94mInitializing {name} in a new terminal")
            process = subprocess.Popen(
                shlex.split(f'gnome-terminal -- bash -c "{command}"')
            )
        else:
            print("Initializing process in a tmux session")
            print(
                f"\033[95mFor access session, use the command: tmux attach -t {name}\033[0m"
            )
            process = subprocess.Popen(
                shlex.split(f'tmux new-session -d -s {name} "{command}"'),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        sleep(1.5)

        # Wait for the process to finish
        stdout, stderr = process.communicate()

        # Check for any errors
        if process.returncode != 0:
            print(f"\033[91mError starting {name}: {process.returncode}\033[0m")
            return False
        else:
            print(f"\033[92mStarted {name} successfully\033[0m")
            return True
