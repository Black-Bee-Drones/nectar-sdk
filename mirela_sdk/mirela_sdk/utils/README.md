# Utilities 🧙‍♂️

This repository provides a powerful utility class, `ProcessUtils` (found in `process.py`), designed to streamline the management of your processes 

## Features 

* **Process Management:** Easily launch, monitor, and terminate processes from within your Python scripts.

    Here's a closer look at the core functionalities of the `ProcessUtils` class:

    | Function/Method | Description |
    |---|---|
    | `is_gui_available()` | Checks if a GUI terminal (gnome-terminal) is present on your system. 🖥️ |
    | `start_process(command, name='my_session', gui=False)` | Launches the specified `command`. If `gui=True` and a GUI is available, it uses gnome-terminal. Otherwise, it defaults to a new tmux session named `name`.  Provides helpful status messages.  |
    | `has_process(name='my_session')` | Checks if a tmux session with the given `name` is running.  🔍 |
    | `kill_process(name='my_session')` | Terminates the tmux session matching the provided `name`.  Validates session existence before attempting termination. ❌ |

