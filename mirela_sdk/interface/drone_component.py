from abc import ABC, abstractmethod

import pathlib
import numpy as np
import threading

from tkinter import *


class DroneComponent(ABC):
    """
    Abstract base class for a drone interface component.
    """

    def __init__(self, root) -> None:
        """
        Initialize the drone component.

        param: root: The root widget used to create other widgets.
        """
        self.drone = None
        self.on: bool = False
        self.recording: bool = False
        self.colors = {
            "yellow": "#FDCE01",
            "black": "#1E1E1E",
            "white": "#FEFEFE",
        }
        self.action = np.zeros(4)

        self.driver_thread = threading.Thread(target=self.init_drone_config)

        self.imgs_dir = pathlib.Path(__file__).parent.resolve()

        self.root = root

    @abstractmethod
    def init_drone_config(self):
        """
        Abstract method to initialize drone configuration.
        """
        pass

    @abstractmethod
    def create_specific_widgets(self):
        """
        Abstract method to create specific widgets.
        """
        pass

    def create_common_widgets(self):
        """
        Method to create common widgets shared to drones interfaces
        """
        self.root.bind(
            "<KeyPress>", lambda event: self.moviment_control(event.keycode, True)
        )
        self.root.bind(
            "<KeyRelease>", lambda event: self.moviment_control(event.keycode, False)
        )

        self.frame_teclas = Frame(
            self.root,
            bg=self.colors["black"],
            background=self.colors["black"],
        )
        self.frame_teclas.grid(row=2, column=0, columnspan=2, padx=80, pady=30)

        self.frame_control = LabelFrame(
            self.root,
            text="Velocity Control",
            padx=20,
            pady=10,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.frame_control.grid(row=1, column=1)

        self.frame_basic = Frame(
            self.root,
            padx=20,
            pady=10,
            bg=self.colors["black"],
            background=self.colors["black"],
        )
        self.frame_basic.grid(row=1, column=0)

        self.frame_camera = LabelFrame(
            self.root,
            text="Camera Menu",
            padx=20,
            pady=10,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.frame_camera.grid(row=3, column=0, columnspan=2)

        self.img_logo = PhotoImage(file=f"{self.imgs_dir}/images/logo.png")
        self.logo = Label(self.root, image=self.img_logo, bg=self.colors["black"])
        self.logo.grid(row=0, column=0, columnspan=2, ipadx=20, ipady=16, padx=20)

        # self.btn_config = Button(
        #     self.root,
        #     text="Configure",
        #     width=6,
        #     command=self.driver_thread.start,
        #     bg=self.colors["black"],
        #     background=self.colors["black"],
        #     fg=self.colors["white"],
        # )
        # self.btn_config.place(x=390, y=25)

        self.btn_W = Button(
            self.frame_teclas,
            text="W",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(0, 0, 1, 0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_W.grid(row=0, column=1)

        self.btn_A = Button(
            self.frame_teclas,
            text="A",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(0, 0, 0, 1),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_A.grid(row=1, column=0)

        self.btn_S = Button(
            self.frame_teclas,
            text="S",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(0, 0, -1, 0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_S.grid(row=1, column=1)

        self.btn_D = Button(
            self.frame_teclas,
            text="D",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(0, 0, 0, -1),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_D.grid(row=1, column=2)

        self.btn_Up = Button(
            self.frame_teclas,
            text="^",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(1, 0, 0, 0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_Up.grid(row=0, column=5)

        self.btn_Left = Button(
            self.frame_teclas,
            text="<",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(0, 1, 0, 0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_Left.grid(row=1, column=4)

        self.btn_Right = Button(
            self.frame_teclas,
            text=">",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(0, -1, 0, 0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_Right.grid(row=1, column=6)

        self.btn_Down = Button(
            self.frame_teclas,
            text="v",
            height=2,
            width=3,
            state=DISABLED,
            command=lambda: self.move(-1, 0, 0, 0),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_Down.grid(row=1, column=5)

        self.btn_on = Button(
            self.frame_teclas,
            text="OFF",
            fg="white",
            bg="#A60305",
            width=2,
            command=self.on_off,
        )
        self.btn_on.grid(row=0, column=3)

        self.keyboard = [
            self.btn_Up,
            self.btn_Left,
            self.btn_W,
            self.btn_A,
            self.btn_Down,
            self.btn_Right,
            self.btn_S,
            self.btn_D,
        ]
        self.keyboard_values = [111, 113, 25, 38, 116, 114, 39, 40]

        self.label_pitch = Label(
            self.frame_control,
            text="Pitch",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_pitch.grid(row=0, column=0)

        self.label_roll = Label(
            self.frame_control,
            text="Roll",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_roll.grid(row=0, column=1)

        self.label_thrust = Label(
            self.frame_control,
            text="Thrust",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_thrust.grid(row=0, column=2)

        self.label_yaw = Label(
            self.frame_control,
            text="Yaw",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_yaw.grid(row=0, column=3)

        self.slide_pitch = Scale(
            self.frame_control,
            from_=1,
            to=0,
            resolution=0.1,
            length=80,
            orient=VERTICAL,
            state=DISABLED,
            bg=self.colors["black"],
            fg=self.colors["white"],
        )
        self.slide_pitch.grid(row=1, column=0)

        self.slide_roll = Scale(
            self.frame_control,
            from_=1,
            to=0,
            resolution=0.1,
            length=80,
            orient=VERTICAL,
            state=DISABLED,
            bg=self.colors["black"],
            fg=self.colors["white"],
        )
        self.slide_roll.grid(row=1, column=1)

        self.slide_thrust = Scale(
            self.frame_control,
            from_=1,
            to=0,
            resolution=0.1,
            length=80,
            orient=VERTICAL,
            state=DISABLED,
            bg=self.colors["black"],
            fg=self.colors["white"],
        )
        self.slide_thrust.grid(row=1, column=2)

        self.slide_yaw = Scale(
            self.frame_control,
            from_=1,
            to=0,
            resolution=0.1,
            length=80,
            orient=VERTICAL,
            state=DISABLED,
            bg=self.colors["black"],
            fg=self.colors["white"],
        )
        self.slide_yaw.grid(row=1, column=3)

        self.slides = [
            self.slide_pitch,
            self.slide_roll,
            self.slide_thrust,
            self.slide_yaw,
        ]

        self.img_camera = PhotoImage(file=f"{self.imgs_dir}/images/camera.png")
        self.img_photo = PhotoImage(file=f"{self.imgs_dir}/images/photo.png")
        self.img_video = PhotoImage(file=f"{self.imgs_dir}/images/video.png")

        self.btn_camera = Button(
            self.frame_camera,
            image=self.img_camera,
            text="Abrir camera",
            command=self.drone.image_viewer,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_camera.grid(row=0, column=0)

        self.btn_photo = Button(
            self.frame_camera,
            image=self.img_photo,
            text="Foto",
            command=self.drone.snapshot,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_photo.grid(row=0, column=1, padx=40)

        self.btn_video = Button(
            self.frame_camera,
            image=self.img_video,
            text="Video",
            command=lambda: self.drone.record(not self.recording),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_video.grid(row=0, column=2)

    def create_widgets(self):
        """
        Create all widgets for the drone component.
        """
        self.create_common_widgets()
        self.create_specific_widgets()

    def on_off(self):
        """
        Turn the keyboard control on or off
        """
        if self.on:
            self.btn_on.config(text="OFF", bg="red")

            for slide in self.slides:
                slide.set(0)
                slide.config(state=DISABLED)

            [key.config(state=DISABLED) for key in self.keyboard]
        else:
            self.btn_on.config(text="ON", bg="green")

            [slide.config(state=NORMAL) for slide in self.slides]
            [key.config(state=NORMAL) for key in self.keyboard]

            self.slide_pitch.set(0.1)
            self.slide_roll.set(0.1)
            self.slide_thrust.set(0.2)
            self.slide_yaw.set(0.2)

        self.on = not self.on

    def move(self, pitch, roll, thrust, yaw):
        """
        Move the drone based on the specified velocities by csliders controllers

        :param pitch: The pitch velocity.
        :param roll: The roll velocity.
        :param thrust: The thrust velocity.
        :param yaw: The yaw velocity.
        """

        velocity = np.array([pitch, roll, thrust, yaw])

        control_velocity = np.array([slide.get() for slide in self.slides])
        velocity = control_velocity * velocity

        if self.on:
            self.drone.offboard_velocity(*velocity)

    def moviment_control(self, key_pressed, hold):
        """
        Control the movement of the drone based on key presses.

        :param key_pressed: The keycode of the pressed key.
        :param hold: Whether the key is being held down.
        """

        for i, key_value in enumerate(self.keyboard_values):
            if key_pressed == key_value:
                self.keyboard[i].config(relief="sunken" if hold else "raised")
                self.action[i % 4] = 1 * hold if (i < 4) else -1 * hold

        self.move(*self.action)
