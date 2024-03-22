from tkinter import *

import pathlib
import numpy as np

import rclpy
from mirela_sdk.control.bebop.bebop_api import Bebop
from mirela_sdk.control.mavros.mavros_api import MavDrone


class DroneGUI:
    def __init__(self, drone: Bebop):

        self.drone = drone
        self.drone
        self.action = np.zeros(4)
        self.on: bool = False
        self.recording: bool = False
        self.colors = {
            "yellow": "#FDCE01",
            "black": "#1E1E1E",
            "white": "#FEFEFE",
        }

        self.imgs_dir = pathlib.Path(__file__).parent.resolve()

        self.init_gui()

        self.window.mainloop()

    def init_gui(self):
        self.root = Tk()
        self.root.title("Drone Interface")
        self.root.configure(bg=self.colors["black"])
        self.root.resizable(False, False)

        w = 500
        h = 500
        w_screen = self.root.winfo_screenwidth()
        h_screen = self.root.winfo_screenheight()
        posx = w_screen / 2 - w / 2
        posy = h_screen / 2 - h / 2
        self.root.geometry("%dx%d+%d+%d" % (w, h, posx, posy))
        self.root.bind(
            "<KeyPress>", lambda event: self.moviment_control(event.keycode, True)
        )
        self.root.bind(
            "<KeyRelease>", lambda event: self.moviment_control(event.keycode, False)
        )

        self.init_widgets()
        self.root.mainloop()

    def init_widgets(self):
        frame_teclas = Frame(
            self.root,
            bg=self.colors["black"],
            background=self.colors["black"],
        )
        frame_teclas.grid(row=2, column=0, columnspan=2, padx=70, pady=30)

        frame_control = LabelFrame(
            self.root,
            text="Velocity Control",
            padx=10,
            pady=10,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        frame_control.grid(row=1, column=1)

        frame_basic = Frame(
            self.root,
            padx=20,
            pady=10,
            bg=self.colors["black"],
            background=self.colors["black"],
        )
        frame_basic.grid(row=1, column=0)

        frame_camera = LabelFrame(
            self.root,
            text="Camera Menu",
            padx=20,
            pady=10,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        frame_camera.grid(row=3, column=0, columnspan=2)

        self.img_logo = PhotoImage(file=f"{self.imgs_dir}/images/logo.png")
        self.logo = Label(self.root, image=self.img_logo, bg=self.colors["black"])
        self.logo.grid(row=0, column=0, columnspan=2, ipadx=20, ipady=16)

        self.btn_W = Button(
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
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
            frame_teclas,
            text="OFF",
            fg="white",
            bg="red",
            width=2,
            command=self.on_off,
            background=self.colors["black"],
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

        self.btn_takeoff = Button(
            frame_basic,
            text="Takeoff",
            width=5,
            command=self.drone.takeoff,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_takeoff.grid(row=0, column=0)

        self.btn_land = Button(
            frame_basic,
            text="Land",
            width=5,
            command=self.drone.land,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_land.grid(row=1, column=0, pady=10)

        self.btn_flip = Button(
            frame_basic,
            text="Flip",
            width=5,
            command=self.open_flip_menu,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_flip.grid(row=2, column=0)

        self.label_pitch = Label(
            frame_control,
            text="Pitch",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_pitch.grid(row=0, column=0)

        self.label_roll = Label(
            frame_control,
            text="Roll",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_roll.grid(row=0, column=1)

        self.label_thrust = Label(
            frame_control,
            text="Thrust",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_thrust.grid(row=0, column=2)

        self.label_yaw = Label(
            frame_control,
            text="Yaw",
            anchor=CENTER,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.label_yaw.grid(row=0, column=3)

        self.slide_pitch = Scale(
            frame_control,
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
            frame_control,
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
            frame_control,
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
            frame_control,
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
            frame_camera,
            image=self.img_camera,
            text="Abrir camera",
            command=self.drone.image_viewer,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_camera.grid(row=0, column=0)

        self.btn_photo = Button(
            frame_camera,
            image=self.img_photo,
            text="Foto",
            command=self.drone.snapshot,
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_photo.grid(row=0, column=1, padx=40)

        self.btn_video = Button(
            frame_camera,
            image=self.img_video,
            text="Video",
            command=lambda: self.drone.record(not self.recording),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_video.grid(row=0, column=2)

    def open_flip_menu(self):

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

    def on_off(self):
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

        velocity = np.array([pitch, roll, thrust, yaw])

        control_velocity = np.array([slide.get() for slide in self.slides])
        velocity = control_velocity * velocity

        if self.on:
            self.drone.offboard_velocity(*velocity)

    def moviment_control(self, key_pressed, hold):

        for i, key_value in enumerate(self.keyboard_values):
            if key_pressed == key_value:
                self.keyboard[i].config(relief="sunken" if hold else "raised")
                self.action[i % 4] = 1 * hold if (i < 4) else -1 * hold

        self.move(*self.action)

    def __del__(self):
        self.drone.land()
        self.drone.destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    gui = DroneGUI(MavDrone())
    rclpy.spin(gui)


if __name__ == "__main__":
    main()
