# Drone Control Package 🚁

Whether you're flying a MAV (Micro Air Vehicle) with MAVROS or a Parrot Bebop 2, this SDK has you covered!  It offers abstract base classes, specific drone implementations, and helpful utilities for tasks like precision landing and GPS control.

## Features ✨

* **Abstract Drone Control:** The `drone.py` module defines an abstract `Drone` class, providing a common interface for controlling different drone types. This allows for easy integration of new drone platforms.
* **MAVROS Integration:**  Control MAV-enabled drones through the `mavros_api.py` module, offering functionalities like takeoff/landing, setting flight modes, GPS control, and more.
* **Parrot Bebop 2 Support:**  Fly your Bebop 2 with ease using the `bebop_api.py` module, providing commands for takeoff/landing, velocity control, flips, camera adjustments, and snapshots.
* **Precision Landing:**  The `precision_landing.py` module enables precise landing using ArUco marker detection, ideal for targeted package delivery.
* **GPS Controller:**  Leverage the `gps_controller.py` module for advanced GPS functionalities like geofencing, geoid height calculations, and bearing/distance calculations.
* **PID Controller:**  The `controller.py` module provides a Python interface to a ROS2 PID control library, allowing for precise control loops.

## Package Structure 📂

* **`control`**: Contains the core drone control logic.
    * **`drone.py`**: Abstract base class for drone control.
    * **`mavros`**:  MAVROS-specific implementation.
        * **`__init__.py`**: Exposes `GPSController`, `MavDrone`, and `PrecisionLanding`.
        * **`gps_controller.py`**:  GPS control functionalities.
        * **`mavros_api.py`**: MAVROS API interaction.
        * **`precision_landing.py`**: Precision landing with ArUco markers.
    * **`bebop`**: Bebop-specific implementation.
        * **`__init__.py`**: Exposes the `Bebop` class.
        * **`bebop_api.py`**: Bebop API interaction.
    * **`pid`**: PID controller implementation.
        * **`__init__.py`**: Exposes the `PIDController` class.
        * **`controller.py`**: PID controller logic.

## Installation ⚙️

```bash
# Clone the repository
git clone <repository_url>

# Install dependencies (replace with your specific ROS2 distribution)
# Example using rosdep:
rosdep install -i --from-paths src --rosdistro <your_ros_distro> -y

# Build the package (using colcon for example)
colcon build
```

## Usage Examples 💡

**Bebop Takeoff and Landing:**

```python
from bebop import Bebop

bebop = Bebop()
bebop.takeoff()
# ... some time later ...
bebop.land()
```

**MAVROS GPS Navigation:**

```python
from mavros import MavDrone, GPSController

drone = MavDrone()
gps_controller = GPSController(drone)

# Define a geofence (latitude, longitude tuples)
gps_controller.geofence([(-22.41517936,-45.44797450),(-22.41493884,-45.44779748),(-22.41532317,-45.44727176)], rtl=True)

# Send a GPS setpoint (latitude, longitude, altitude, heading)
gps_controller.gps_send(-22.415, -45.447, 10, 0)
```
