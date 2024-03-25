import subprocess
import shlex


from tkinter import *

from mirela_sdk.interface.drone_component import DroneComponent
from mirela_sdk.control.mavros.mavros_api import MavDrone


class MavComponent(DroneComponent):

    def __init__(self, root):
        """
        Initialize a MavComponent.

        :param root: The root tkinter window.
        """

        super().__init__(root)

        print("Mav component Init")

        self.drone = MavDrone()

    def init_drone_config(self):
        """
        Initialize the Mavros configuration for the Mav drone.
        """

        # Command to start the ros2 launch mavros apm
        command = [
            "ros2",
            "launch",
            "mavros",
            "apm.launch",
            "fcu_url:=serial:///dev/ttyUSB0:57600",
        ]

        # Join the list elements into a single string
        command_str = " ".join(command)

        # Start the process
        process = subprocess.Popen(
            shlex.split(f'gnome-terminal -- bash -c "{command_str}"')
        )

        # Wait for the process to finish
        stdout, stderr = process.communicate()

        # Check for any errors
        if process.returncode != 0:
            print(f"\033[91mErro ao iniciar o mavros: {process.returncode}\033[0m")
        else:
            print(f"\033[92mMavros apm launch iniciado com sucesso\033[0m")

    def create_specific_widgets(self):
        """
        Create specific widgets for the Mav drone component.
        """

        self.btn_arm = Button(
            self.frame_basic,
            text="Arm",
            width=5,
            command=lambda: self.drone.arm(),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_arm.grid(row=0, column=0, padx=10)

        self.btn_disarm = Button(
            self.frame_basic,
            text="Disarm",
            width=5,
            command=lambda: self.drone.kill_motors(),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_disarm.grid(row=0, column=1)

        self.btn_takeoff = Button(
            self.frame_basic,
            text="Takeoff",
            width=5,
            command=lambda: self.drone.takeoff(1.0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_takeoff.grid(row=1, column=0, pady=10, padx=10)

        self.btn_land = Button(
            self.frame_basic,
            text="Land",
            width=5,
            command=self.drone.land,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_land.grid(row=1, column=1)

        self.btn_arm_takeoff = Button(
            self.frame_basic,
            text="Arm Takeoff",
            width=10,
            command=lambda: self.drone.arm_takeoff(1.0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_arm_takeoff.grid(row=3, column=0, columnspan=15, pady=20, padx=10)
