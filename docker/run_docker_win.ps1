# =============================================================================
# Nectar SDK - Docker Helper for Windows (PowerShell)
# =============================================================================
#
# Usage:
#   .\run_docker_win.ps1 build  [distro] [variant]
#   .\run_docker_win.ps1 verify [distro] [variant]
#   .\run_docker_win.ps1 test   [distro] [variant] [-Modules "vision control"]
#   .\run_docker_win.ps1 run    [distro] [variant] [-NoUsb]
#   .\run_docker_win.ps1 exec
#   .\run_docker_win.ps1 usb    list|attach|bind|detach|check [realsense|webcam|all]
#
# Examples:
#   .\run_docker_win.ps1 build humble
#   .\run_docker_win.ps1 build jazzy full-cpu
#   .\run_docker_win.ps1 verify humble                 # tier-1: install/imports/nodes
#   .\run_docker_win.ps1 test humble                   # tier-1 + tier-2 (pytest suite)
#   .\run_docker_win.ps1 test humble -Modules "vision" # tier-2 subset by marker
#   .\run_docker_win.ps1 run humble
#   .\run_docker_win.ps1 exec
# =============================================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("build", "verify", "test", "run", "exec", "usb", "help")]
    [string]$Command = "help",

    [Parameter(Position=1)]
    [string]$Distro = "humble",

    # CUDA variants must match a wheel index that ships the pinned torch
    # (scripts/lib/config.sh TORCH_VERSION). torch 2.9.x ships cu126/cu128/cu130,
    # not cu124. full-cpu always works.
    [Parameter(Position=2)]
    [string]$Variant = "",

    # Optional pytest marker subset for `test` (maps to `verify-functional`),
    # e.g. -Modules "vision control". Empty runs the full functional suite.
    [string]$Modules = "",

    # `usb` subcommand: list, attach, bind, detach, check
    [string]$UsbAction = "",

    # `usb` target: realsense, webcam, all
    [string]$UsbTarget = "",

    [switch]$AutoAttach,
    [switch]$Realsense,
    [switch]$NoUsb
)

# Resolve paths from the script location so the helper works from any CWD.
$RepoRoot = Split-Path $PSScriptRoot -Parent
$ImagePrefix = "nectar-sdk"
$ContainerPrefix = "nectar"
$DockerfilePath = Join-Path $PSScriptRoot "Dockerfile"
. (Join-Path $PSScriptRoot "lib\windows_usb.ps1")

function Show-Help {
    Write-Host ""
    Write-Host "Nectar SDK - Docker Helper for Windows" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\run_docker_win.ps1 build  [distro] [variant]"
    Write-Host "  .\run_docker_win.ps1 verify [distro] [variant]"
    Write-Host "  .\run_docker_win.ps1 test   [distro] [variant] [-Modules `"vision control`"]"
    Write-Host "  .\run_docker_win.ps1 run    [distro] [variant]"
    Write-Host "  .\run_docker_win.ps1 exec"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  build     Build the SDK image"
    Write-Host "  verify    Tier-1 check inside the image (install / imports / nodes)"
    Write-Host "  test      Tier-1 + tier-2 (pytest functional suite); JUnit -> ci-local-results\"
    Write-Host "  run       Start an interactive container (GUI + GPU + USB when available)"
    Write-Host "  exec      Attach a new shell to a running container"
    Write-Host "  usb       List/bind/attach USB devices (usbipd-win)"
    Write-Host ""
    Write-Host "Arguments:"
    Write-Host "  distro    ROS 2 distribution: humble (default), jazzy, kilted"
    Write-Host "  variant   Build variant: full-cpu, full-cu126, full-cu128 (full builds only)"
    Write-Host "  -Modules  pytest marker subset for 'test' (e.g. 'vision control')"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\run_docker_win.ps1 build humble"
    Write-Host "  .\run_docker_win.ps1 build jazzy full-cpu"
    Write-Host "  .\run_docker_win.ps1 verify humble"
    Write-Host "  .\run_docker_win.ps1 test humble"
    Write-Host "  .\run_docker_win.ps1 test humble -Modules `"vision control`""
    Write-Host "  .\run_docker_win.ps1 run humble"
    Write-Host "  .\run_docker_win.ps1 exec"
    Write-Host "  .\run_docker_win.ps1 usb list"
    Write-Host "  .\run_docker_win.ps1 usb attach realsense -AutoAttach"
    Write-Host "  .\run_docker_win.ps1 build jazzy full-cu126 -Realsense"
    Write-Host ""
}

function Show-UsbHelp {
    Write-Host ""
    Write-Host "USB (usbipd-win + Docker Desktop)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  usb list                  Show devices and docker-desktop video nodes"
    Write-Host "  usb bind   <target>       Bind device (admin once): realsense | webcam | all"
    Write-Host "  usb attach <target>       Attach to docker-desktop WSL VM"
    Write-Host "  usb detach <busid>        Detach by bus ID (from usb list)"
    Write-Host "  usb check  [distro] [variant]  Probe USB inside a throwaway container"
    Write-Host ""
    Write-Host "Targets: realsense, webcam, all"
    Write-Host "Add -AutoAttach to re-attach after unplug/reboot."
    Write-Host ""
}

function Assert-RosDistro([string]$name) {
    if ($name -notin @("humble", "jazzy", "kilted")) {
        Write-Host "ERROR: Invalid ROS distro '$name' (humble, jazzy, kilted)" -ForegroundColor Red
        exit 1
    }
}

function Resolve-UsbInvocation {
    if ($Command -ne "usb") { return }
    if ($script:Distro -in @("humble", "jazzy", "kilted")) {
        if (-not $script:UsbAction) { $script:UsbAction = "list" }
        return
    }
    if (-not $script:UsbAction) { $script:UsbAction = $script:Distro }
    if ($script:UsbAction -eq "check" -and $script:Variant -in @("humble", "jazzy", "kilted")) {
        $script:Distro = $script:Variant
        $script:Variant = ""
        return
    }
    if ($script:UsbAction -in @("attach", "bind") -and $script:Variant -and $script:Variant -notmatch "^full-") {
        $script:UsbTarget = $script:Variant
        $script:Variant = ""
    }
    if ($script:UsbAction -eq "detach" -and $script:Variant) {
        $script:UsbTarget = $script:Variant
        $script:Variant = ""
    }
    $script:Distro = "jazzy"
}

function Assert-Variant([string]$name) {
    if (-not $name) { return }
    if ($name -notin @("full-cpu", "full-cu124", "full-cu126", "full-cu128")) {
        Write-Host "ERROR: Invalid variant '$name' (full-cpu, full-cu126, full-cu128)" -ForegroundColor Red
        exit 1
    }
}

function Build-Image {
    Assert-RosDistro $Distro
    Assert-Variant $Variant
    $imageTag = "$ImagePrefix`:$Distro"
    $target = "sdk"
    $installRs = if ($Realsense) { "true" } else { "false" }
    $buildArgs = @(
        "--build-arg", "ROS_DISTRO=$Distro",
        "--build-arg", "INSTALL_REALSENSE=$installRs",
        "--build-arg", "REALSENSE_CUDA=false"
    )

    if ($Variant) {
        $torchVariant = $Variant -replace "^full-", ""
        $imageTag = "$ImagePrefix`:$Distro-full-$torchVariant"
        $target = "sdk-full"
        $buildArgs += "--target", $target
        $buildArgs += "--build-arg", "TORCH_VARIANT=$torchVariant"
    } else {
        $buildArgs += "--target", $target
    }

    Write-Host "Building Docker image: $imageTag" -ForegroundColor Green
    Write-Host "ROS Distro: $Distro"
    if ($Variant) { Write-Host "Variant: $Variant" }
    if ($Realsense) { Write-Host "RealSense: enabled (+15-20 min build)" }
    Write-Host ""

    $dockerArgs = @(
        "build",
        "--network=host"
    ) + $buildArgs + @(
        "-t", $imageTag,
        "-f", $DockerfilePath,
        $RepoRoot
    )

    & docker $dockerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Build failed" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Successfully built: $imageTag" -ForegroundColor Green
}

# Compute the image tag for the current Distro/Variant. Matches the Linux naming
# (nectar-sdk:<distro>-full-<torch>), so the "full-" prefix on Variant is stripped.
function Resolve-ImageTag {
    if ($Variant) {
        $tv = $Variant -replace "^full-", ""
        return "$ImagePrefix`:$Distro-full-$tv"
    }
    return "$ImagePrefix`:$Distro"
}

# Return @("--gpus","all") when the daemon exposes the NVIDIA runtime, else @().
# Reads `docker info` (no image pull) so it is fast and never fails the run.
# Returns the flag as separate tokens because `& docker` passes each array
# element as its own argument.
function Get-GpuFlag {
    try {
        $runtimes = docker info --format "{{json .Runtimes}}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $runtimes -match "nvidia") {
            Write-Host "NVIDIA runtime detected (adding --gpus all)" -ForegroundColor Green
            return @("--gpus", "all")
        }
    } catch {
        # daemon unreachable or no GPU runtime; run without GPU
    }
    return @()
}

# Fail fast with a clear message if the requested image is not built yet.
function Assert-ImageExists([string]$imageTag) {
    $images = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -SimpleMatch $imageTag
    if (-not $images) {
        Write-Host "ERROR: Image $imageTag not found. Build it first:" -ForegroundColor Red
        Write-Host "  .\run_docker_win.ps1 build $Distro $Variant"
        exit 1
    }
}

function Run-Container {
    Assert-RosDistro $Distro
    $imageTag = Resolve-ImageTag
    Assert-ImageExists $imageTag

    $containerName = "$ContainerPrefix`_$Distro"
    if ($Variant) {
        $tv = $Variant -replace "^full-", ""
        $containerName = "$ContainerPrefix`_$Distro-full-$tv"
    }

    # Remove existing container if it exists
    docker rm -f $containerName 2>$null | Out-Null

    Write-Host "Starting container: $containerName" -ForegroundColor Green
    Write-Host "Image: $imageTag"
    Write-Host ""

    $gpuFlag = Get-GpuFlag

    # Windows X11 display setup
    $displayVar = "host.docker.internal:0.0"

    $usbFlags = @()
    if (-not $NoUsb) {
        $usbFlags = Get-DockerUsbRunFlags
        Write-Host "USB: /dev/bus/usb mounted (attach devices with: usb attach realsense)" -ForegroundColor Cyan
    }

    $dockerArgs = @(
        "run", "-it", "--rm",
        "--name=$containerName",
        "--env=DISPLAY=$displayVar",
        "--env=QT_X11_NO_MITSHM=1",
        "--privileged"
    ) + $gpuFlag + $usbFlags + @($imageTag, "bash")

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

# Source ROS + the SDK overlay, then run an inner command inside a throwaway
# container. Mirrors scripts/ci_local.sh `_in_image`: $ROS_DISTRO and the overlay
# come from the image, so the source lines stay single-quoted (expanded in the
# container, not by PowerShell).
$SetupInImage = "/home/ros2_ws/src/nectar-sdk/scripts/setup.sh"
$SourcePrefix = 'source /opt/ros/$ROS_DISTRO/setup.bash; source /home/ros2_ws/install/local_setup.bash 2>/dev/null || true; '

# Tier-1: install / imports / nodes (scripts/setup.sh verify).
# Pipes docker output to the host stream so callers can capture only the exit
# code (return value), not the streamed container logs.
function Verify-Image {
    $imageTag = Resolve-ImageTag
    Assert-ImageExists $imageTag
    Write-Host "Tier-1 verify on $imageTag ..." -ForegroundColor Green
    $inner = $SourcePrefix + "$SetupInImage verify"
    $dArgs = @("run", "--rm") + (Get-GpuFlag) + @($imageTag, "bash", "-lc", $inner)
    docker @dArgs | Out-Host
    return $LASTEXITCODE
}

# Tier-1 + Tier-2: verify, then the pytest functional suite. JUnit report is
# written to <repo>\ci-local-results on the host. -Modules subsets the markers.
function Test-Image {
    $imageTag = Resolve-ImageTag
    Assert-ImageExists $imageTag

    $resultsHost = Join-Path $RepoRoot "ci-local-results"
    New-Item -ItemType Directory -Force -Path $resultsHost | Out-Null

    Write-Host ""
    Write-Host "=== Tier-1: verify (install / imports / nodes) ===" -ForegroundColor Cyan
    $verifyRc = Verify-Image

    Write-Host ""
    Write-Host "=== Tier-2: verify-functional (pytest) ===" -ForegroundColor Cyan
    if ($Modules) { Write-Host "Marker subset: $Modules" }
    $junit = "/tmp/results/functional-windows-$Distro.xml"
    $funcInner = $SourcePrefix + "JUNIT_XML=$junit $SetupInImage verify-functional"
    if ($Modules) { $funcInner += " $Modules" }
    $dArgs = @("run", "--rm") + (Get-GpuFlag) + @("--volume", "${resultsHost}:/tmp/results", $imageTag, "bash", "-lc", $funcInner)
    docker @dArgs
    $funcRc = $LASTEXITCODE

    Write-Host ""
    Write-Host "=============== SUMMARY ($imageTag) ===============" -ForegroundColor Cyan
    $v = if ($verifyRc -eq 0) { "PASS" } else { "FAIL" }
    $f = if ($funcRc -eq 0) { "PASS" } else { "FAIL" }
    $vc = if ($verifyRc -eq 0) { "Green" } else { "Red" }
    $fc = if ($funcRc -eq 0) { "Green" } else { "Red" }
    Write-Host ("  tier-1 verify:            {0}" -f $v) -ForegroundColor $vc
    Write-Host ("  tier-2 verify-functional: {0}" -f $f) -ForegroundColor $fc
    Write-Host "  JUnit report: $(Join-Path $resultsHost ("functional-windows-$Distro.xml"))"
    Write-Host ""
    if ($verifyRc -ne 0 -or $funcRc -ne 0) { exit 1 }
}

function Invoke-UsbCommand {
    $action = if ($UsbAction) { $UsbAction.ToLower() } else { "help" }

    switch ($action) {
        "list" { Show-UsbList; return }
        "help" { Show-UsbHelp; return }
        "bind" {
            if (-not $UsbTarget) { Show-UsbHelp; exit 1 }
            $kinds = if ($UsbTarget -eq "all") { @("realsense", "webcam") } else { @($UsbTarget) }
            foreach ($k in $kinds) {
                $dev = Find-UsbDevice -Kind $k
                if (-not $dev) { Write-Host "Not found: $k" -ForegroundColor Yellow; continue }
                Invoke-UsbipdBind -BusId $dev.BusId | Out-Null
            }
            return
        }
        "attach" {
            if (-not $UsbTarget) { Show-UsbHelp; exit 1 }
            if (-not (Invoke-UsbAttachKind -Kind $UsbTarget -AutoAttach:$AutoAttach)) { exit 1 }
            Show-UsbList
            return
        }
        "detach" {
            if (-not $UsbTarget) { Show-UsbHelp; exit 1 }
            if (-not (Invoke-UsbipdDetach -BusId $UsbTarget)) { exit 1 }
            return
        }
        "check" {
            $imageTag = Resolve-ImageTag
            Assert-ImageExists $imageTag
            $inner = 'apt-get update -qq && apt-get install -y -qq usbutils 2>/dev/null; echo "=== lsusb ==="; lsusb; echo "=== video ==="; ls -la /dev/video* 2>&1; if command -v rs-enumerate-devices >/dev/null; then echo "=== realsense ==="; rs-enumerate-devices 2>&1 | head -20; else echo "=== realsense === not installed (rebuild with -Realsense)"; fi'
            $dArgs = @("run", "--rm", "--privileged") + (Get-DockerUsbRunFlags) + @($imageTag, "bash", "-lc", $inner)
            docker @dArgs
            return
        }
        default { Show-UsbHelp; exit 1 }
    }
}

# Main
Resolve-UsbInvocation
switch ($Command) {
    "build" {
        Build-Image
    }
    "verify" {
        $rc = Verify-Image
        if ($rc -ne 0) { exit $rc }
    }
    "test" {
        Test-Image
    }
    "run" {
        Assert-RosDistro $Distro
        Run-Container
    }
    "exec" {
        Exec-Container
    }
    "usb" {
        Invoke-UsbCommand
    }
    default {
        Show-Help
    }
}
