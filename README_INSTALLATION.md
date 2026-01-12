# Mirela SDK - Installation Guide 🦥

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Ubuntu | 22.04+ | Tested on 22.04 LTS |
| Disk Space | 10GB+ | ROS2 + dependencies |
| RAM | 4GB min, 8GB+ recommended | For AI module |
| Python | 3.10+ | Included with Ubuntu 22.04 |

## Quick Install 🚀

```bash
wget https://raw.githubusercontent.com/Black-Bee-Drones/mirela-sdk/main/scripts/install_env.sh
chmod +x install_env.sh
./install_env.sh
```

The script automatically installs:
- System packages (git, cmake, build-essential)
- [ROS2 Humble](https://docs.ros.org/en/humble/) + [MAVROS](https://github.com/mavlink/mavros)
- [GeographicLib](https://geographiclib.sourceforge.io/) datasets (EGM96 geoid)
- mirela-sdk repository
- Python dependencies

## Manual Installation 👨🏻‍💻

### 1. ROS2 Humble

Follow the [official ROS2 Humble installation](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) or use:

```bash
# Add ROS2 repository
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/ros2.list

# Install ROS2 + MAVROS
sudo apt update
sudo apt install -y ros-humble-desktop-full \
    ros-humble-mavros ros-humble-mavros-extras \
    ros-humble-vision-opencv \
    python3-colcon-common-extensions python3-rosdep

# Initialize rosdep
sudo rosdep init
rosdep update
```

### 2. GeographicLib (for MAVROS)

Required for GPS coordinate transformations:

```bash
sudo /opt/ros/humble/lib/mavros/install_geographiclib_datasets.sh
```

### 3. Clone Repository

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone git@github.com:Black-Bee-Drones/mirela-sdk.git
```

### 4. Python Dependencies

**Core** (vision, control, cameras):
```bash
pip install -r mirela-sdk/requirements.txt
```

**AI/Detection** (optional):
```bash
# PyTorch - select based on your hardware
# CPU only:
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cpu

# CUDA 12.4 (NVIDIA GPU):
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu124

# AI module dependencies
pip install -r mirela-sdk/requirements-ai.txt
```

See [PyTorch Get Started](https://pytorch.org/get-started/locally/) for other configurations.

### 5. Build Workspace

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install -i --from-path src --rosdistro humble -r -y
colcon build --symlink-install
```

### 6. Environment Setup

Add to `~/.bashrc`:
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/local_setup.bash
```

Then reload:
```bash
source ~/.bashrc
```

## Optional Hardware 📷

### Intel RealSense D435i

For depth camera support (indoor navigation, obstacle detection):

```bash
cd ~/ros2_ws/src/mirela-sdk
./scripts/install_realsense.sh
```

Or install manually following the [librealsense installation guide](https://github.com/IntelRealSense/librealsense/blob/master/doc/distribution_linux.md).

### Luxonis OAK-D

DepthAI is included in `requirements.txt`. For troubleshooting, see [DepthAI installation](https://docs.luxonis.com/software/depthai/manual-install/).

## Verify Installation ✅

```bash
source ~/.bashrc

# Check ROS2
ros2 pkg list | grep mirela

# Should output:
# mirela_interfaces
# mirela_sdk

# Test GUI
ros2 run mirela_sdk gui

# Test camera
ros2 run mirela_sdk camera_example
```

## Troubleshooting 🔧

### ROS2 not found

```bash
source /opt/ros/humble/setup.bash
```

### mirela_sdk package not found

```bash
cd ~/ros2_ws
colcon build --symlink-install
source install/local_setup.bash
```

### Python packages missing

```bash
pip install -r ~/ros2_ws/src/mirela-sdk/requirements.txt
```

### Camera permission denied

```bash
sudo usermod -a -G video $USER
# Logout and login required
```

### OpenCV headless error

If using SSH or headless environment:
```bash
pip uninstall opencv-python-headless
pip install opencv-python
```

### MAVROS connection issues

Check serial permissions:
```bash
sudo usermod -a -G dialout $USER
# Logout and login required
```

Verify MAVROS connection:
```bash
ros2 run mavros mavros_node --ros-args -p fcu_url:=serial:///dev/ttyUSB0:921600
```

## Update 🔄

```bash
cd ~/ros2_ws/src/mirela-sdk
git pull origin main
cd ~/ros2_ws
colcon build --symlink-install
source install/local_setup.bash
```

## Docker Alternative 🐳

For a pre-configured environment, see [`docker/README.md`](docker/README.md):

```bash
# Linux
./docker/run_docker_linux.sh

# Windows (PowerShell)
.\docker\run_docker_win.ps1
```
