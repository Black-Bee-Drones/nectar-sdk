# Direct MAVLink Control

A direct [pymavlink](https://mavlink.io/en/mavgen_python/) path for cases where the [MAVROS](../mavros/README.md) bridge is unavailable, undesired, or insufficient. Currently ships only the connection wrapper used by companion-side sensor publishers (e.g. [`RangefinderPublisher`](../../sensors/rangefinder_publisher.py)).

A full `MavlinkDrone` parallel to [`MavrosDrone`](../mavros/drone.py) — implementing the same `Drone` protocol but talking pymavlink directly — is planned but not yet implemented.

## Current scope

### `MavlinkConnection`

Thin wrapper around `mavutil.mavlink_connection` in [`connection.py`](connection.py). Opens a single MAVLink endpoint to the FCU, performs the heartbeat handshake to discover `target_system` / `target_component`, and exposes the raw pymavlink connection via `.master` so callers can send any MAVLink message.

```python
from nectar.control import MavlinkConnection
from pymavlink import mavutil

conn = MavlinkConnection(
    source_system=1,
    source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER,
    heartbeat_timeout=30.0,
)

conn.connect("udp:127.0.0.1:14551")            # UDP listener
# or
conn.connect("/dev/ttyUSB0", baud=921600)      # serial
# or
conn.connect("tcp:192.168.1.10:5760")          # TCP

conn.master.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0,
)

conn.close()
```

## Planned: `MavlinkDrone`

A future addition will provide a `MavlinkDrone(BaseDrone)` implementing the full [`Drone` protocol](../protocols.py) (connect, arm, takeoff, land, move_velocity, move_to, move_to_gps, rtl, ...) directly via pymavlink, so missions can run without MAVROS. It will be registered with [`DroneFactory`](../factory.py) as the `"mavlink"` drone type and will reuse `MavlinkConnection` as its transport.

Until that lands, use [`MavrosDrone`](../mavros/README.md) for full drone control. `MavlinkConnection` is enough on its own for simple message-publishing tasks (sensors, custom commands, telemetry probes).

## References

- [pymavlink documentation](https://mavlink.io/en/mavgen_python/)
- [MAVLink common messages](https://mavlink.io/en/messages/common.html)
- [ArduPilot MAVLink basics](https://ardupilot.org/dev/docs/mavlink-basics.html)
- [mavlink-router](https://github.com/mavlink-router/mavlink-router) — fan out the FCU's serial to multiple endpoints (MAVROS + this connection)
