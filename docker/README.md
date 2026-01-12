# Docker Environment for Mirela SDK 🐳

Multi-stage Docker setup for outdoor GPS-based drone control and indoor VSLAM operations. Includes MAVROS, computer vision support, and Intel RealSense D435i integration.

## 🐳 Multi-Stage Docker Environment

### Available Images:

1. **`mirela-sdk:base`** - Base image with ROS2 Humble, MAVROS, and computer vision support
2. **`mirela-sdk:realsense`** - Extended image with RealSense D435i support and VSLAM capabilities

### Key Features:

#### Base Image (`mirela-sdk:base`):
* **ROS2 Humble Desktop Full:** Complete ROS2 Humble desktop installation
* **MAVROS & MAVROS Extras:** Communication with MAVLink-compatible autopilots
* **Computer Vision Support:** `vision_opencv` for image processing
* **Custom SDK Integration:** `mirela-sdk` with all Python dependencies
* **GeographicLib Datasets:** Essential geographic data for MAVROS
* **Pre-configured Environment:** ROS2 environment ready to use

#### RealSense Image (`mirela-sdk:realsense`):
* **All Base Features:** Everything from the base image
* **Intel RealSense D435i Support:** Complete librealsense2 installation with CUDA support
* **RealSense ROS2 Driver:** `realsense-ros` package for ROS2 integration
* **Vision to MAVROS:** `vision_to_mavros` for indoor pose estimation
* **VSLAM Ready:** Optimized for indoor navigation tasks
* **CUDA Acceleration:** GPU-accelerated processing on Jetson platforms

### 🛠️ Building the Docker Images

#### Automated Build (Recommended):
```bash
# Build all images
./build_images.sh all

# Or build specific images
./build_images.sh base       # Only base image
./build_images.sh realsense  # Only RealSense image
```

#### Manual Build:
```bash
# Build base image
docker build --network=host -t mirela-sdk:base -f Dockerfile.base .

# Build RealSense image (requires base image)
docker build --network=host -t mirela-sdk:realsense -f Dockerfile.realsense .
```

## 🏎️ Running the Docker Containers

### Linux: [`run_docker_linux.sh`](run_docker_linux.sh) 🐧

The updated script supports both image types with flexible options:

#### Usage Examples:

```bash
# Run base image (default)
./run_docker_linux.sh --base

# Run RealSense image
./run_docker_linux.sh --realsense

# Build and run RealSense image
./run_docker_linux.sh --realsense --build

# Custom container name
./run_docker_linux.sh --realsense --name my_custom_container

# Show help
./run_docker_linux.sh --help
```

#### Key Features:

* **Multi-Image Support:** Choose between base and RealSense images
* **X11 Forwarding:** Graphical applications display on host X server
* **Device Mounting:** Access to cameras (`/dev/video0`, `/dev/video1`) and USB devices
* **Volume Mounting:** Mount host workspace for development
* **Host Networking:** Shared network access with host
* **Privileged Mode:** Full access to hardware devices

#### Container Specifications:

**Base Container:**
- Image: `mirela-sdk:base`
- Use case: Outdoor GPS-based drone control
- Dependencies: MAVROS, vision_opencv, mirela-sdk

**RealSense Container:**
- Image: `mirela-sdk:realsense`
- Use case: Indoor VSLAM with RealSense D435i
- Dependencies: All base + librealsense2, realsense-ros, vision_to_mavros

### Windows Support

Windows scripts are available but may need updates for the new multi-stage setup. For Windows development, consider using WSL2 with the Linux scripts above.

## 🎯 Usage Scenarios

### Outdoor GPS-Based Missions
For outdoor competitions with GPS availability:
```bash
# Use base image for GPS navigation
./run_docker_linux.sh --base

# Inside container, run your GPS-based control scripts
ros2 run mirela_sdk gps_control_node
```

### Indoor VSLAM Missions
For indoor environments with RealSense D435i:
```bash
# Use RealSense image for indoor navigation
./run_docker_linux.sh --realsense

# Inside container, launch RealSense and vision_to_mavros
ros2 launch realsense2_camera rs_launch.py
ros2 launch vision_to_mavros t265_tf_to_mavros_launch.py
```

### Development Workflow
For active development and testing:
```bash
# Mount your host workspace for live editing
./run_docker_linux.sh --realsense --name dev_container

# Your changes in ~/ros2_ws/src/mirela-sdk will be reflected immediately
```

## 🔧 Best Practices

### Environment Selection
- **Use `base` image** for outdoor GPS missions (smaller, faster)
- **Use `realsense` image** for indoor VSLAM missions (includes RealSense support)
- **Both images** can run simultaneously with different container names

### Performance Optimization
- **Jetson Orin Nano:** Use RealSense image for CUDA acceleration
- **Raspberry Pi:** Use base image to save resources
- **Development:** Use volume mounting for live code editing

### Container Management
- **Persistent data:** Use named containers for development
- **Clean restarts:** Containers auto-remove on exit (use `--name` to persist)
- **Resource monitoring:** Use `docker stats` to monitor resource usage

## Docker Installation Guide

### Windows

1. Download the [Docker Desktop installer](https://docs.docker.com/desktop/setup/install/windows-install/#install-from-the-command-line).
2. Open the folder containing the installer in Command Prompt (run as Administrator).
3. Install Docker Desktop using the command line for greater control over installation options:

    ```bash
    start /w "" "Docker Desktop Installer.exe" install -accept-license --installation-dir="D:\Docker\Docker" --wsl-default-data-root="D:\Docker\wsl" --windows-containers-default-data-root="D:\Docker"
    ```

    - This setup allows customization of the installation directory and the default location for WSL (Docker images).
    - Customizing these paths is especially useful if your primary drive (e.g., `C:`) has limited space.

4. Optionally, install [XLaunch](https://sourceforge.net/projects/vcxsrv/) to enable GUI applications in Docker. Configure the `DISPLAY` environment variable in Docker and launch applications with GUI support.

### Linux (Ubuntu)

1. Add Docker’s official GPG key and repository:

    ```bash
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    ```

2. Download the latest `.deb` file for Docker Desktop from the [official release notes](https://docs.docker.com/desktop/release-notes/).
3. Install Docker Desktop and Docker Engine:

    ```bash
    sudo apt-get update
    sudo apt-get install ./docker-desktop-amd64.deb
    sudo apt-get install docker-ce
    ```

## 📝 Notes

* Ensure Docker is installed and running on your system.
* The `--net=host` option provides the container full access to the host's network. While convenient, this should be used with caution due to security implications.
* The scripts assume the `Dockerfile` is located in the `docker/` directory.





