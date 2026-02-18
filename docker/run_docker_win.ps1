# =============================================================================
# Nectar SDK - Docker Helper for Windows (PowerShell)
# =============================================================================
#
# Usage:
#   .\run_docker_win.ps1 build [distro] [variant]
#   .\run_docker_win.ps1 run [distro] [variant]
#   .\run_docker_win.ps1 exec
#
# Examples:
#   .\run_docker_win.ps1 build humble
#   .\run_docker_win.ps1 build jazzy full-cpu
#   .\run_docker_win.ps1 run humble
#   .\run_docker_win.ps1 exec
# =============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("build", "run", "exec", "help")]
    [string]$Command = "help",

    [Parameter(Position=1)]
    [ValidateSet("humble", "jazzy", "kilted")]
    [string]$Distro = "humble",

    [Parameter(Position=2)]
    [ValidateSet("full-cpu", "full-cu124")]
    [string]$Variant = ""
)

$ImagePrefix = "nectar-sdk"
$ContainerPrefix = "nectar"
$DockerfilePath = "docker\Dockerfile"

function Show-Help {
    Write-Host ""
    Write-Host "Nectar SDK - Docker Helper for Windows" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run_docker_win.ps1 build [distro] [variant]"
    Write-Host "  .\run_docker_win.ps1 run [distro] [variant]"
    Write-Host "  .\run_docker_win.ps1 exec"
    Write-Host ""
    Write-Host "Arguments:"
    Write-Host "  distro    ROS 2 distribution: humble (default), jazzy, kilted"
    Write-Host "  variant  Build variant: full-cpu, full-cu124 (for full builds only)"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\run_docker_win.ps1 build humble"
    Write-Host "  .\run_docker_win.ps1 build jazzy full-cpu"
    Write-Host "  .\run_docker_win.ps1 run humble"
    Write-Host "  .\run_docker_win.ps1 exec"
    Write-Host ""
}

function Build-Image {
    $imageTag = "$ImagePrefix`:$Distro"
    $target = "sdk"
    $buildArgs = @(
        "--build-arg", "ROS_DISTRO=$Distro",
        "--build-arg", "INSTALL_REALSENSE=false",
        "--build-arg", "REALSENSE_CUDA=false"
    )

    if ($Variant) {
        $imageTag = "$ImagePrefix`:$Distro-full-$Variant"
        $target = "sdk-full"
        $torchVariant = $Variant -replace "full-", ""
        $buildArgs += "--target", $target
        $buildArgs += "--build-arg", "TORCH_VARIANT=$torchVariant"
    } else {
        $buildArgs += "--target", $target
    }

    Write-Host "Building Docker image: $imageTag" -ForegroundColor Green
    Write-Host "ROS Distro: $Distro"
    if ($Variant) {
        Write-Host "Variant: $Variant"
    }
    Write-Host ""

    $dockerArgs = @(
        "build",
        "--network=host"
    ) + $buildArgs + @(
        "-t", $imageTag,
        "-f", $DockerfilePath,
        "."
    )

    & docker $dockerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Build failed" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Successfully built: $imageTag" -ForegroundColor Green
}

function Run-Container {
    $imageTag = "$ImagePrefix`:$Distro"
    if ($Variant) {
        $imageTag = "$ImagePrefix`:$Distro-full-$Variant"
    }

    # Check if image exists
    $images = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -Pattern $imageTag
    if (-not $images) {
        Write-Host "ERROR: Image $imageTag not found. Build it first:" -ForegroundColor Red
        Write-Host "  .\run_docker_win.ps1 build $Distro $Variant"
        exit 1
    }

    $containerName = "$ContainerPrefix`_$Distro"
    if ($Variant) {
        $containerName = "$ContainerPrefix`_$Distro-full-$Variant"
    }

    # Remove existing container if it exists
    docker rm -f $containerName 2>$null | Out-Null

    Write-Host "Starting container: $containerName" -ForegroundColor Green
    Write-Host "Image: $imageTag"
    Write-Host ""

    # Check for NVIDIA GPU (Windows Docker Desktop)
    $gpuFlag = ""
    try {
        docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $gpuFlag = "--gpus all"
            Write-Host "GPU support detected" -ForegroundColor Green
        }
    } catch {
        # GPU not available
    }

    # Windows X11 display setup
    $displayVar = "host.docker.internal:0.0"

    $dockerArgs = @(
        "run", "-it", "--rm",
        "--name=$containerName",
        "--env=DISPLAY=$displayVar",
        "--env=QT_X11_NO_MITSHM=1",
        "--privileged"
    )

    if ($gpuFlag) {
        $dockerArgs += $gpuFlag
    }

    $dockerArgs += $imageTag, "bash"

    & docker $dockerArgs
}

function Exec-Container {
    Write-Host "Finding running containers..." -ForegroundColor Cyan

    $containers = docker ps --format "{{.Names}}" | Select-String -Pattern $ContainerPrefix
    if (-not $containers) {
        Write-Host "ERROR: No running Nectar SDK containers found" -ForegroundColor Red
        Write-Host "Start a container first: .\run_docker_win.ps1 run"
        exit 1
    }

    Write-Host ""
    Write-Host "Running containers:" -ForegroundColor Cyan
    docker ps --format "table {{.Names}}\t{{.Image}}" | Select-String -Pattern $ContainerPrefix
    Write-Host ""

    $containerName = Read-Host "Enter container name"
    if (-not $containerName) {
        Write-Host "ERROR: Container name required" -ForegroundColor Red
        exit 1
    }

    Write-Host "Attaching to $containerName..." -ForegroundColor Green
    docker exec -it $containerName bash
}

# Main
switch ($Command) {
    "build" {
        Build-Image
    }
    "run" {
        Run-Container
    }
    "exec" {
        Exec-Container
    }
    default {
        Show-Help
    }
}
