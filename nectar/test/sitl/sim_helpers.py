"""Sim-lifecycle orchestration for the SITL/integration test tier.

Each firmware/protocol entry is described by a :class:`SimSpec`: the shell
commands that bring the simulator up (reusing the proven ``make sim-start`` /
``make sim-bridge`` entry points), the SDK drone type + config preset to fly it
with, and a minimal smoke-flight envelope (takeoff altitude, a short move).

The functions here start the sim as background processes, wait until the SDK can
connect and the vehicle is settled (this is what removes the EKF/prearm timing
flakiness of a fresh boot), and tear everything down with ``make sim-stop``.

Plain Python (no pytest) so it imports cheaply at collection; ``nectar`` and the
config presets are imported lazily inside the lifecycle functions. Named
``sim_helpers`` (not ``helpers``) to avoid clashing with ``test/helpers.py``.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, List

# nectar-sdk repo root (where the Makefile lives): test/sitl/sim_helpers.py -> repo.
REPO_DIR = str(Path(__file__).resolve().parents[3])
_LOG_DIR = os.path.join(os.environ.get("TMPDIR", "/tmp"), "nectar-sitl")


@dataclasses.dataclass
class SimSpec:
    """One firmware/protocol simulation target and its smoke-flight envelope."""

    key: str
    firmware: str  # ardupilot | px4 | crazyflie  (pytest marker)
    drone_type: str  # DroneFactory key
    config_factory: Callable[[], object]  # lazily builds the SDK config (start_driver=False)
    start_cmds: List[str]  # shell commands to bring the sim up, in order
    gps: bool = True  # wait for a GPS fix before flying (outdoor FCU)
    crazyflie: bool = False  # needs the crazyflie_server killed explicitly on teardown
    alt: float = 2.0
    move_x: float = 1.5
    precision: float = 0.4
    connect_timeout: float = 150.0
    settle: float = 15.0  # post-connect EKF/prearm settle before takeoff


def _no_driver(config):
    """Force start_driver off: the test owns the sim lifecycle, not the SDK."""
    if dataclasses.is_dataclass(config) and hasattr(config, "start_driver"):
        return dataclasses.replace(config, start_driver=False)
    return config


def _ardupilot_mavros():
    from nectar.control import SITL_GPS_CONFIG

    return _no_driver(SITL_GPS_CONFIG)


def _ardupilot_mavlink():
    from nectar.control import MAVLINK_SITL_GAZEBO_CONFIG

    return _no_driver(MAVLINK_SITL_GAZEBO_CONFIG)


def _px4_mavros():
    from nectar.control import PX4_SITL_CONFIG

    return _no_driver(PX4_SITL_CONFIG)


def _px4_mavlink():
    from nectar.control import PX4_MAVLINK_SITL_CONFIG

    return _no_driver(PX4_MAVLINK_SITL_CONFIG)


def _px4_dds():
    from nectar.control import PX4_DDS_SITL_CONFIG

    return _no_driver(PX4_DDS_SITL_CONFIG)


def _crazyflie():
    from nectar.control import CrazyflieConfig

    return CrazyflieConfig(cf_name="cf231", backend="sim", mocap=False, start_driver=False)


_AP_START = "make sim-start FIRMWARE=ardupilot ENV=outdoor"
_PX4_START = "make sim-start FIRMWARE=px4 ENV=outdoor ARGS=--headless"
_AP_BRIDGE = "make sim-bridge FIRMWARE=ardupilot ENV=outdoor PROTOCOL={proto} ARGS=headless:=true"

SIM_SPECS = {
    "ardupilot-mavros": SimSpec(
        key="ardupilot-mavros",
        firmware="ardupilot",
        drone_type="mavros",
        config_factory=_ardupilot_mavros,
        start_cmds=[_AP_START, _AP_BRIDGE.format(proto="mavros")],
        settle=90.0,  # ArduPilot EKF + gyro-consistency prearm needs time to converge
    ),
    "ardupilot-mavlink": SimSpec(
        key="ardupilot-mavlink",
        firmware="ardupilot",
        drone_type="mavlink",
        config_factory=_ardupilot_mavlink,
        # MAVLINK_SITL_GAZEBO_CONFIG uses SERIAL1 (tcp 5762); ArduPilot only opens it
        # once SERIAL0 (5760) has a client, so run the mavros bridge alongside to
        # unblock it (matches `sitl_test.py --mavlink`).
        start_cmds=[_AP_START, _AP_BRIDGE.format(proto="mavros")],
        settle=90.0,
    ),
    "px4-mavros": SimSpec(
        key="px4-mavros",
        firmware="px4",
        drone_type="px4",
        config_factory=_px4_mavros,
        start_cmds=[_PX4_START, "make sim-bridge FIRMWARE=px4 ENV=outdoor PROTOCOL=mavros"],
    ),
    "px4-mavlink": SimSpec(
        key="px4-mavlink",
        firmware="px4",
        drone_type="px4_mavlink",
        config_factory=_px4_mavlink,
        start_cmds=[_PX4_START, "make sim-bridge FIRMWARE=px4 ENV=outdoor PROTOCOL=mavlink"],
    ),
    "px4-dds": SimSpec(
        key="px4-dds",
        firmware="px4",
        drone_type="px4_dds",
        config_factory=_px4_dds,
        start_cmds=[_PX4_START, "make sim-bridge FIRMWARE=px4 ENV=outdoor PROTOCOL=dds"],
    ),
    "crazyflie-sim": SimSpec(
        key="crazyflie-sim",
        firmware="crazyflie",
        drone_type="crazyflie",
        config_factory=_crazyflie,
        start_cmds=["ros2 launch crazyflie launch.py backend:=sim mocap:=False teleop:=False"],
        gps=False,
        crazyflie=True,
        alt=0.5,
        move_x=0.5,
        precision=0.2,
        connect_timeout=60.0,
        settle=3.0,
    ),
}

SIM_KEYS = list(SIM_SPECS)


def crazyflie_sim_available() -> bool:
    """True if the Crazyswarm2 sim backend (``crazyflie_sim``) is installed.

    The apt ``crazyflie`` package does not ship it; it needs a Crazyswarm2 source
    build. The crazyflie SITL case self-skips when this returns False.
    """
    try:
        from ament_index_python.packages import get_package_prefix

        get_package_prefix("crazyflie_sim")
        return True
    except Exception:  # noqa: BLE001
        return False


def start_sim(spec: SimSpec) -> List[subprocess.Popen]:
    """Bring the simulator up as background processes; log each to a file."""
    os.makedirs(_LOG_DIR, exist_ok=True)
    handles: List[subprocess.Popen] = []
    for i, cmd in enumerate(spec.start_cmds):
        log_path = os.path.join(_LOG_DIR, f"{spec.key}_{i}.log")
        log = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 - closed by process exit
        handles.append(
            subprocess.Popen(cmd, cwd=REPO_DIR, shell=True, stdout=log, stderr=subprocess.STDOUT)
        )
        # Let the simulator come up before the bridge connects to it.
        time.sleep(12 if i == 0 and len(spec.start_cmds) > 1 else 2)
    return handles


def connect_drone(spec: SimSpec):
    """Create the SDK drone and wait until connected, GPS-locked and settled.

    Returns the connected drone, or None if it never came up within the timeout.
    """
    import nectar
    from nectar.control import DroneFactory

    nectar.init()

    # Retry creation too: some transports connect on construction (a direct-MAVLink
    # TCP link raises ConnectionRefused until the autopilot's serial port is up),
    # so creating once outside the loop would error before the sim is ready.
    drone = None
    deadline = time.monotonic() + spec.connect_timeout
    connected = False
    while time.monotonic() < deadline:
        try:
            if drone is None:
                drone = DroneFactory.create(spec.drone_type, spec.config_factory())
            if drone.connect():
                connected = True
                break
        except Exception:  # noqa: BLE001 - sim/port not up yet; retry create + connect
            drone = None
            time.sleep(3.0)
            continue
        time.sleep(2.0)
    if not connected:
        return None

    if spec.gps:
        gps_deadline = time.monotonic() + 45.0
        while time.monotonic() < gps_deadline:
            gps = getattr(drone, "gps", None)
            if gps is not None and getattr(gps, "latitude", 0.0) != 0.0:
                break
            time.sleep(1.0)

    time.sleep(spec.settle)
    return drone


def teardown(drone, handles: List[subprocess.Popen], spec: SimSpec) -> None:
    """Land/clean the drone, stop the SDK runtime, and kill all sim processes."""
    import nectar

    if drone is not None:
        try:
            drone.land(timeout=20.0)
        except Exception:  # noqa: BLE001
            pass
        try:
            drone.cleanup()
        except Exception:  # noqa: BLE001
            pass
    try:
        nectar.shutdown()
    except Exception:  # noqa: BLE001
        pass

    subprocess.run(
        "make sim-stop",
        cwd=REPO_DIR,
        shell=True,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if spec.crazyflie:
        subprocess.run(
            "pkill -f crazyflie_server; pkill -f 'ros2 launch crazyflie'",
            shell=True,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    for h in handles:
        try:
            h.terminate()
            h.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                h.kill()
            except Exception:  # noqa: BLE001
                pass
