# [![dock](https://img.icons8.com/?size=30&id=GZxgGaKN8jxz&format=png&color=000000)](#) Docker Environment for BlackBee Project

This repository provides a streamlined Docker setup for developing and running the BlackBee project within a ROS2 Humble environment. It includes MAVROS, computer vision support (vision_opencv), and a custom SDK (mirela-sdk). The provided scripts simplify the build and execution process across Linux and Windows operating systems.

## 🐳 Dockerized ROS2 Humble Environment

The core of this setup is a Docker image built using the provided [`Dockerfile`](Dockerfile). This image encapsulates all the necessary dependencies, ensuring a consistent and reproducible development environment.

### Key Features:

* **ROS2 Humble Desktop Full:** Provides the complete ROS2 Humble desktop installation.
* **MAVROS & MAVROS Extras:** Enables communication with MAVLink-compatible autopilots.
* **Computer Vision Support:** Integrates `vision_opencv` for image processing and computer vision tasks.
* **Custom SDK Integration:** Includes the `mirela-sdk` and installs its Python dependencies.
* **GeographicLib Datasets:** Provides necessary geographic data.
* **Pre-configured Environment:** Configures the ROS2 environment within the container.

### 🛠️ Building the Docker Image

The `Dockerfile` handles the image creation process, installing all required packages and dependencies, including:

* `nano`, `git`, `python3-pip`, `python3-colcon-common-extensions`, `tmux`, `wget`
* `ros-humble-mavros`, `ros-humble-mavros-extras`, `ros-humble-tf-transformations`, `ros-humble-ament-cmake`

It also clones the `vision_opencv` repository, copies the local `mirela-sdk` repository, installs its Python dependencies, and builds the ROS2 workspace using `colcon`.

## 🏎️ Running the Docker Container

Platform-specific scripts are provided for seamless execution:

### Linux: [`run_docker_linux.sh`](run_docker_linux.sh) 🐧

This bash script builds and runs the Docker container named `ros2_black_bee`. Key functionalities include:

* **X11 Forwarding:** Enables graphical applications within the container to display on the host X server.
* **Device Mounting:** Mounts `/dev/video0` inside the container, likely for camera access.
* **Host Networking:** Uses `--net=host` for shared network access (use with caution!).

**Usage:**

```bash
bash run_docker_linux.sh
```

### Windows: [`run_docker_win.ps1`](run_docker_win.ps1) & [`run_docker_win.cmd`](run_docker_win.cmd) 🪟

Both scripts achieve the same goal on Windows: building and running the `ros2_black_bee` container. They handle setting the `DISPLAY` environment variable for GUI applications and use host networking.

**PowerShell Usage:**

```powershell
.\run_docker_win.ps1
```

**Command Prompt Usage:**

```cmd
run_docker_win.cmd
```

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





