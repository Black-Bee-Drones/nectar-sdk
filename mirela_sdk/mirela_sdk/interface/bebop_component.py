from rclpy.node import Node

from tkinter import *
import numpy as np

from mirela_sdk.interface.drone_component import DroneComponent
from mirela_sdk.control.bebop.bebop_api import Bebop


class BebopComponent(DroneComponent):

    def __init__(self, root, node: Node) -> None:
        """
        Initialize a BebopComponent.

        :param root: The root tkinter window.
        :param node: The ROS2 node.
        """

        super().__init__(root, node)

        print("Bebop component Init")

        self.drone = Bebop(node, driver=False)

    def update_state(self, on: bool):
        super().update_state(on)
        if on:
            self.btn_takeoff.config(state="normal")
            self.btn_land.config(state="normal")
            self.btn_flip.config(state="normal")
        else:
            self.btn_takeoff.config(state=DISABLED)
            self.btn_land.config(state=DISABLED)
            self.btn_flip.config(state=DISABLED)

    def create_specific_widgets(self):
        """
        Create specific widgets for the Bebop drone component.
        """

        self.btn_takeoff = Button(
            self.frame_basic,
            text="Takeoff",
            width=5,
            command=self.drone.takeoff,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
            state=DISABLED,
        )
        self.btn_takeoff.grid(row=0, column=0)

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
        self.btn_land.grid(row=1, column=0, pady=10)

        self.btn_flip = Button(
            self.frame_basic,
            text="Flip",
            width=5,
            command=self.open_flip_menu,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
            state=DISABLED,
        )
        self.btn_flip.grid(row=2, column=0)

    def move_velocity(self, velocity: np.ndarray) -> None:
        """
        Move the drone based on the specified velocities.
        """
        self.drone.offboard_velocity(*velocity)

    def open_flip_menu(self):
        """
        Open the flip menu for the Bebop drone.
        """

        flip_menu = Toplevel(
            bg=self.colors["black"],
            background=self.colors["black"],
        )
        flip_menu.title("Flip menu")
        flip_menu.geometry("+500+500")
        flip_menu.configure(bg=self.colors["black"])
        flip_menu.resizable(False, False)

        frame_flip = Frame(
            flip_menu,
            padx=20,
            pady=20,
            bg=self.colors["black"],
            background=self.colors["black"],
        )

        btn_flip_front = Button(
            frame_flip,
            text="Front",
            height=2,
            width=6,
            command=lambda: [self.drone.flip(0), flip_menu.destroy()],
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        btn_flip_back = Button(
            frame_flip,
            text="Back",
            height=2,
            width=6,
            command=lambda: [self.drone.flip(1), flip_menu.destroy()],
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        btn_flip_left = Button(
            frame_flip,
            text="Left",
            height=2,
            width=6,
            command=lambda: [self.drone.flip(2), flip_menu.destroy()],
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        btn_flip_right = Button(
            frame_flip,
            text="Right",
            height=2,
            width=6,
            command=lambda: [self.drone.flip(3), flip_menu.destroy()],
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )

        btn_flip_front.grid(row=0, column=1)
        btn_flip_back.grid(row=2, column=1)
        btn_flip_left.grid(row=1, column=0)
        btn_flip_right.grid(row=1, column=2)
        frame_flip.pack()
