# USB device helpers for Docker Desktop on Windows (usbipd-win).
# Requires: https://github.com/dorssel/usbipd-win

$script:RealSenseVidPid = "8086:0b3a"

function Test-UsbipdAvailable {
    return [bool](Get-Command usbipd -ErrorAction SilentlyContinue)
}

function Get-UsbipdRows {
    if (-not (Test-UsbipdAvailable)) { return @() }

    $rows = @()
    $section = ""
    foreach ($line in (& usbipd list 2>&1 | ForEach-Object { "$_" })) {
        $line = $line.Trim()
        if (-not $line) { continue }
        if ($line -match "^Connected:") { $section = "connected"; continue }
        if ($line -match "^Persisted:") { $section = "persisted"; continue }
        if ($section -ne "connected") { continue }
        if ($line -notmatch "^\d+-\d+") { continue }

        $parts = ($line -split '\s+') | Where-Object { $_ }
        if ($parts.Count -lt 2) { continue }
        $busId = $parts[0]
        $vidPid = if ($parts[1] -match '^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$') { $parts[1] } else { "" }
        $state = "Unknown"
        if ($line -match '(Not shared|Shared|Attached)\s*$') { $state = $Matches[1] }

        $name = $line.Substring($busId.Length).Trim()
        if ($vidPid) { $name = ($name -replace "^\s*$([regex]::Escape($vidPid))\s+", "").Trim() }
        $name = ($name -replace '\s+(Not shared|Shared|Attached)\s*$', '').Trim()

        $rows += [pscustomobject]@{
            BusId  = $busId
            VidPid = $vidPid
            Name   = $name
            State  = $state
        }
    }
    return $rows
}

function Find-UsbDevice {
    param(
        [ValidateSet("realsense", "webcam")]
        [string]$Kind
    )

    $rows = Get-UsbipdRows
    switch ($Kind) {
        "realsense" {
            return $rows | Where-Object {
                $_.VidPid -eq $script:RealSenseVidPid -or $_.Name -match "RealSense"
            } | Select-Object -First 1
        }
        "webcam" {
            return $rows | Where-Object {
                $_.Name -match "Facing|Webcam|Camera|UVC" -and
                $_.Name -notmatch "RealSense"
            } | Select-Object -First 1
        }
    }
}

function Invoke-UsbipdBind {
    param([string]$BusId)

    $out = usbipd bind --busid $BusId 2>&1
    if ($LASTEXITCODE -eq 0) { return $true }

    if ($out -match "Access denied|administrator") {
        Write-Host "Admin required (one-time per device):" -ForegroundColor Yellow
        Write-Host "  usbipd bind --busid $BusId"
        return $false
    }
    Write-Host $out -ForegroundColor Red
    return $false
}

function Invoke-UsbipdAttach {
    param(
        [string]$BusId,
        [switch]$AutoAttach
    )

    $args = @("attach", "--wsl", "docker-desktop", "--busid", $BusId)
    if ($AutoAttach) { $args += "--auto-attach" }

    & usbipd @args 2>&1 | ForEach-Object { Write-Host $_ }
    return ($LASTEXITCODE -eq 0)
}

function Invoke-UsbipdDetach {
    param([string]$BusId)
    & usbipd detach --busid $BusId 2>&1 | ForEach-Object { Write-Host $_ }
    return ($LASTEXITCODE -eq 0)
}

function Get-DockerDesktopVideoNodes {
    $raw = wsl -d docker-desktop -e sh -c "ls /dev/video* 2>/dev/null" 2>$null
    if (-not $raw) { return @() }
    return $raw.Trim() -split "\s+" | Where-Object { $_ }
}

function Get-DockerUsbRunFlags {
    $flags = @(
        "-v", "/dev/bus/usb:/dev/bus/usb",
        "--device-cgroup-rule=c 81:* rmw",
        "--device-cgroup-rule=c 189:* rmw"
    )

    foreach ($node in (Get-DockerDesktopVideoNodes)) {
        $flags += "--device=$node"
    }
    return $flags
}

function Show-UsbList {
    if (-not (Test-UsbipdAvailable)) {
        Write-Host "usbipd not found. Install: https://github.com/dorssel/usbipd-win/releases" -ForegroundColor Red
        return
    }

    Write-Host ""
    Write-Host "USB devices (usbipd list):" -ForegroundColor Cyan
    usbipd list
    Write-Host ""

    $rs = Find-UsbDevice -Kind realsense
    $cam = Find-UsbDevice -Kind webcam
    if ($rs) {
        Write-Host "RealSense: $($rs.BusId) ($($rs.VidPid)) [$($rs.State)]" -ForegroundColor Green
    } else {
        Write-Host "RealSense: not detected" -ForegroundColor Yellow
    }
    if ($cam) {
        Write-Host "Webcam:    $($cam.BusId) ($($cam.VidPid)) [$($cam.State)]" -ForegroundColor Green
    } else {
        Write-Host "Webcam:    not detected" -ForegroundColor Yellow
    }

    $videos = Get-DockerDesktopVideoNodes
    if ($videos.Count -gt 0) {
        Write-Host "Video nodes in docker-desktop: $($videos -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "Video nodes in docker-desktop: none (no UVC driver - OpenCV webcam unavailable)" -ForegroundColor Yellow
    }
    Write-Host ""
}

function Invoke-UsbAttachKind {
    param(
        [ValidateSet("realsense", "webcam", "all")]
        [string]$Kind,
        [switch]$AutoAttach
    )

    if (-not (Test-UsbipdAvailable)) {
        Write-Host "ERROR: usbipd not installed" -ForegroundColor Red
        return $false
    }

    $kinds = if ($Kind -eq "all") { @("realsense", "webcam") } else { @($Kind) }
    $ok = $true

    foreach ($k in $kinds) {
        $dev = Find-UsbDevice -Kind $k
        if (-not $dev) {
            Write-Host "Skip $k - not found in usbipd list" -ForegroundColor Yellow
            continue
        }
        if ($dev.State -eq "Not shared") {
            Write-Host "Binding $($dev.BusId) ($($dev.Name))..." -ForegroundColor Cyan
            if (-not (Invoke-UsbipdBind -BusId $dev.BusId)) { $ok = $false; continue }
        }
        Write-Host "Attaching $($dev.BusId) to docker-desktop..." -ForegroundColor Cyan
        if (-not (Invoke-UsbipdAttach -BusId $dev.BusId -AutoAttach:$AutoAttach)) { $ok = $false }
    }
    return $ok
}
