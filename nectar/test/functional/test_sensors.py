"""Sensors functional tests (no serial hardware).

The obstacle-mask filter is driven with a synthetic step-drop stream to confirm
its masking logic; the rangefinder publisher is wired to a loopback FCU and we
assert a real ``DISTANCE_SENSOR`` MAVLink message comes out. The physical TF-Luna
UART driver lives in ``test/hardware`` (it needs a serial device).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.sensors


def test_obstacle_mask_filter():
    """The obstacle-mask filter engages on a step drop and releases when the surface returns."""
    from nectar.sensors.filters.obstacle_mask import ObstacleMaskFilter

    flt = ObstacleMaskFilter(max_change_m=0.30, avg_window=5, timeout_s=None)

    for _ in range(8):
        flt.process(2.0)
    assert not flt.is_masking, "masking engaged on a flat baseline"

    out_entry = flt.process(1.3)
    assert flt.is_masking, "did not enter masking on a 0.7 m step drop"
    assert out_entry > 1.3, f"masked output {out_entry:.2f} not lifted above raw 1.30"

    flt.process(2.1)
    assert not flt.is_masking, "did not exit masking when the surface returned"


def test_rangefinder_to_mavlink(fake_fcu):
    """A rangefinder reading is emitted as a DISTANCE_SENSOR message to the loopback FCU."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers

    from nectar.sensors.rangefinder_publisher import RangefinderPublisher

    class _FakeSensor:
        def read(self):
            return 1.23  # meters

        def close(self):
            pass

    conn = helpers.mavlink_connection_to(fake_fcu.port)
    pub = RangefinderPublisher(
        _FakeSensor(), conn, rate_hz=50.0, min_distance_m=0.05, max_distance_m=8.0
    )
    pub.start()
    try:
        msg = fake_fcu.wait_for("DISTANCE_SENSOR", timeout=3.0)
    finally:
        pub.stop()

    assert msg is not None, "no DISTANCE_SENSOR received over the loopback"
    assert abs(msg.current_distance - 123) <= 2, f"distance {msg.current_distance} cm != ~123 cm"
