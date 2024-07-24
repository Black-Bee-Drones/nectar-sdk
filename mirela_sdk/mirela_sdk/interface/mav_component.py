from rclpy.node import Node


from tkinter import *
import numpy as np

from mirela_sdk.interface.drone_component import DroneComponent
from mirela_sdk.control.mavros.mavros_api import MavDrone


class MavComponent(DroneComponent):

    def __init__(self, root: Tk, node: Node):
        """
        Initialize a MavComponent.

        :param root: The root tkinter window.
        """

        super().__init__(root, node)

        print("Mav component Init")

        self.drone = MavDrone(node, mavros=False)
        self.ground_reference = BooleanVar()

    # Override the update_state method
    def update_state(self, on: bool):
        super().update_state(on)
        if on:
            self.btn_arm.config(state="normal")
            self.btn_disarm.config(state="normal")
            self.btn_takeoff.config(state="normal")
            self.btn_land.config(state="normal")
            self.btn_arm_takeoff.config(state="normal")
        else:
            self.btn_arm.config(state=DISABLED)
            self.btn_disarm.config(state=DISABLED)
            self.btn_takeoff.config(state=DISABLED)
            self.btn_land.config(state=DISABLED)
            self.btn_arm_takeoff.config(state=DISABLED)

    # Override the on_off method
    def on_off(self):
        """
        Turn the keyboard control on or off
        """
        super().on_off()
        if self.on:
            self.btn_ground_reference.config(state="normal")
        else:
            self.btn_ground_reference.config(state=DISABLED)

    def create_specific_widgets(self):
        """
        Create specific widgets for the Mav drone component.
        """

        self.btn_arm = Button(
            self.frame_basic,
            text="Arm",
            width=5,
            command=self.drone.arm,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
            state=DISABLED,
        )
        self.btn_arm.grid(row=0, column=0, padx=10)

        self.btn_disarm = Button(
            self.frame_basic,
            text="Disarm",
            width=5,
            command=self.drone.kill_motors,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
            state=DISABLED,
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
            state=DISABLED,
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
            state=DISABLED,
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
            state=DISABLED,
        )
        self.btn_arm_takeoff.grid(row=3, column=0, columnspan=15, pady=20, padx=10)

        self.btn_ground_reference = Checkbutton(
            self.frame_control,
            state=DISABLED,
            variable=self.ground_reference,
            onvalue=True,
            offvalue=False,
            bg=self.colors["black"],
            fg=self.colors["red"],
            text="Ground Reference",
        )
        self.btn_ground_reference.grid(row=2, column=0, columnspan=15, pady=10)

    def move_velocity(self, velocity: np.ndarray) -> None:
        """
        Move the drone based on the specified velocities.
        """
        self.drone.offboard_velocity(*velocity, self.ground_reference.get())
