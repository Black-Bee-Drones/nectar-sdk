"""Sensors functional checks (no serial hardware).

The obstacle-mask filter is driven with a synthetic step-drop stream to confirm
its masking logic; the rangefinder publisher is wired to a loopback FCU and we
assert a real ``DISTANCE_SENSOR`` MAVLink message comes out. The physical TF-Luna
UART driver self-skips (needs a serial device).
"""

from __future__ import annotations

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec, Skip


def _obstacle_mask_filter() -> str:
    from nectar.sensors.filters.obstacle_mask import ObstacleMaskFilter

    flt = ObstacleMaskFilter(max_change_m=0.30, avg_window=5, timeout_s=None)

    # Establish a ~2.0 m baseline; must not mask.
    for _ in range(8):
        flt.process(2.0)
    if flt.is_masking:
        raise Fail("masking engaged on a flat baseline")

    # Step drop of 0.7 m (> max_change) = crossing an obstacle: enter masking,
    # and the reported distance is lifted back toward the baseline.
    out_entry = flt.process(1.3)
    if not flt.is_masking:
        raise Fail("did not enter masking on a 0.7 m step drop")
    if out_entry <= 1.3:
        raise Fail(f"masked output {out_entry:.2f} not lifted above raw 1.30")

    # Raw rises back above entry+max_change: exit masking, pass raw through.
    flt.process(2.1)
    if flt.is_masking:
        raise Fail("did not exit masking when the surface returned")

    return f"masked a 0.7 m step (out={out_entry:.2f} m) then released"


def _rangefinder_to_mavlink() -> str:
    helpers.require_module("pymavlink", "pymavlink not installed (make python-sensors)")
    from nectar.sensors.rangefinder_publisher import RangefinderPublisher

    class _FakeSensor:
        def read(self):
            return 1.23  # meters

        def close(self):
            pass

    port = helpers.free_udp_port()
    fcu = helpers.FakeFcu(port).start()
    pub = None
    conn = None
    try:
        conn = helpers.mavlink_connection_to(port)
        pub = RangefinderPublisher(
            _FakeSensor(), conn, rate_hz=50.0, min_distance_m=0.05, max_distance_m=8.0
        )
        pub.start()
        msg = fcu.wait_for("DISTANCE_SENSOR", timeout=3.0)
    finally:
        if pub is not None:
            pub.stop()
        fcu.stop()

    if msg is None:
        raise Fail("no DISTANCE_SENSOR received over the loopback")
    if abs(msg.current_distance - 123) > 2:
        raise Fail(f"distance {msg.current_distance} cm != expected ~123 cm")
    return f"DISTANCE_SENSOR over MAVLink: {msg.current_distance} cm"


def _tfluna_serial() -> str:
    raise Skip("requires a TF-Luna on a serial/UART port")


MODULE = ModuleSpec(
    key="sensors",
    title="Sensors",
    install="make python-sensors",
    checks=[
        Check("obstacle-mask filter (step drop)", _obstacle_mask_filter),
        Check("rangefinder -> MAVLink DISTANCE_SENSOR", _rangefinder_to_mavlink),
        Check("TF-Luna serial driver", _tfluna_serial),
    ],
)
