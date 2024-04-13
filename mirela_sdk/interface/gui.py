from tkinter import *
from tkinter import ttk

import threading

import rclpy

from mirela_sdk.interface.drone_component import DroneComponent
from mirela_sdk.interface.bebop_component import BebopComponent
from mirela_sdk.interface.mav_component import MavComponent

from mirela_sdk.control.bebop.bebop_api import Bebop


class DroneGUI:
    def __init__(self):
        """
        Initialize the Drone Graphical User Interface.
        """

        self.drone_strategy: DroneComponent = None
        self.drone = None
        self.colors = {
            "yellow": "#FDCE01",
            "black": "#1E1E1E",
            "white": "#FEFEFE",
        }

        self.init_gui()

    def init_gui(self) -> None:
        """
        Initialize the GUI for the DroneGUI.
        Init root window and style.
        """

        self.root = Tk()
        self.root.title("Drone Interface")
        self.root.configure(bg=self.colors["black"])
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["black"],
            background="gray",
            foreground="white",
        )
        style.configure(
            "TProgressbar",
            foreground=self.colors["black"],
            background=self.colors["yellow"],
            fieldbackground=self.colors["black"],
            troughcolor=self.colors["black"],
        )
        style.map(
            "TCombobox",
            selectbackground=[("readonly", self.colors["black"])],
            selectforeground=[("readonly", self.colors["white"])],
        )
        self.root.option_add("*TCombobox*Listbox*Background", "gray")
        self.root.option_add("*TCombobox*Listbox*Foreground", self.colors["white"])

        w = 520
        h = 540
        w_screen = self.root.winfo_screenwidth()
        h_screen = self.root.winfo_screenheight()
        posx = w_screen / 2 - w / 2
        posy = h_screen / 2 - h / 2
        self.root.geometry("%dx%d+%d+%d" % (w, h, posx, posy))

        self.combobox = ttk.Combobox(
            self.root,
            values=["Bebop", "Mavros"],
            width=10,
            justify="center",
            style="TCombobox",
        )
        self.combobox.bind("<<ComboboxSelected>>", self.update_drone)
        self.combobox.grid(row=0, column=0)
        self.combobox.current(0)

        self.update_drone(None)
        self.init_widgets()
        self.root.mainloop()

    def init_widgets(self) -> None:
        """
        Initialize the widgets for the DroneGUI.
        """

        self.combobox = ttk.Combobox(
            self.root,
            values=["Bebop", "Mavros"],
            width=10,
            justify="center",
            style="TCombobox",
        )
        self.combobox.bind("<<ComboboxSelected>>", self.update_drone)
        self.combobox.grid(row=0, column=0)
        self.combobox.set(self.drone_type)

        self.btn_config = Button(
            self.root,
            text="Configure",
            width=6,
            command=lambda: self.progress_bar(self.drone_strategy.init_drone_config),
            bg=self.colors["black"],
            background=self.colors["black"],
            fg=self.colors["white"],
        )
        self.btn_config.place(x=390, y=25)

    def progress_bar(self, callback) -> None:
        # Clear old widgets and create new ones
        for widget in self.root.winfo_children():
            widget.destroy()

        progress = ttk.Progressbar(
            self.root, length=100, mode="determinate", maximum=140, style="TProgressbar"
        )

        self.root.update()

        # Get dimensions of root and progress bar
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        progress_width = progress.winfo_reqwidth()
        progress_height = progress.winfo_reqheight()

        # Calculate central position
        x = (root_width - progress_width) / 2
        y = (root_height - progress_height) / 2

        # Position progress bar
        progress.place(x=x, y=y)
        progress.start()

        # Start drone initialization in a new thread
        drone_thread = threading.Thread(target=callback)
        drone_thread.start()

        while drone_thread.is_alive():
            self.root.update()

        # Stop and remove progress bar
        progress.stop()
        progress.place_forget()

        self.init_widgets()
        self.drone_strategy.create_widgets()

    def update_drone(self, event) -> None:
        """
        Update the drone based on the selected type on the combobox.

        :param event: The event that triggered the update.
        """
        # Disable the combobox
        self.drone_type = self.combobox.get()
        self.combobox.set(self.drone_type)

        self.combobox.config(state="disabled")

        def init_drone():
            print("Drone set: ", self.drone_type)
            if self.drone_type == "Bebop":
                self.drone_strategy = BebopComponent(self.root)
            elif self.drone_type == "Mavros":
                self.drone_strategy = MavComponent(self.root)
            else:
                return

            if self.drone is not None:
                self.drone.destroy_node()

            self.drone = self.drone_strategy.drone

        self.progress_bar(init_drone)

        # Enable the combobox
        self.combobox.config(state="normal")
        self.combobox.set(self.drone_type)

        def __del__(self):
            """
            Ensure the drone lands and its node is destroyed when the DroneGUI is deleted.
            """

            self.drone_strategy.drone.land()
            self.drone_strategy.drone.destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    gui = DroneGUI()
    rclpy.spin(gui)


if __name__ == "__main__":
    main()
