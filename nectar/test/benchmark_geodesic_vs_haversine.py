#!/usr/bin/env python3
"""
Benchmark: Haversine (spherical) vs Geodesic.WGS84.Inverse (ellipsoidal).

Methodology:
  1. Use Geodesic.WGS84.Direct to place point B at an EXACT known distance
     and bearing from point A. This is the ground truth.
  2. Measure both haversine and Geodesic.Inverse against this known distance.
  3. Compare errors and timing.

Reference:
  Karney, C.F.F. "Algorithms for geodesics", J. Geodesy 87, 43-55 (2013)
  https://doi.org/10.1007/s00190-012-0578-z
  GeographicLib accuracy: ~15 nanometers on WGS84 ellipsoid.

Run: python -m pytest nectar/test/benchmark_geodesic_vs_haversine.py -v -s
"""

import time

import numpy as np
from geographiclib.geodesic import Geodesic

from nectar.utils.gps_calculate import GPSCalculate


def _place_point(lat1, lon1, azimuth, distance_m):
    g = Geodesic.WGS84.Direct(lat1, lon1, azimuth, distance_m)
    return g["lat2"], g["lon2"]


def haversine_and_bearing(lat1, lon1, lat2, lon2):
    dist = GPSCalculate.haversine(lat1, lon1, lat2, lon2)
    brng = GPSCalculate.bearing(lat1, lon1, lat2, lon2)
    return dist, brng


def geodesic_inverse(lat1, lon1, lat2, lon2):
    result = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
    dist = result["s12"]
    brng = result["azi1"] % 360
    return dist, brng


def benchmark_timing(func, lat1, lon1, lat2, lon2, iterations=10000):
    """Time a function over N iterations, return mean µs."""
    start = time.perf_counter()
    for _ in range(iterations):
        func(lat1, lon1, lat2, lon2)
    elapsed = time.perf_counter() - start
    return (elapsed / iterations) * 1e6


# (origin_lat, origin_lon, azimuth_deg, exact_distance_m, description)
EXACT_CASES = [
    # Sub-10m (drone precision range)
    (0.0, 0.0, 90.0, 1.0, "1m East at equator"),
    (0.0, 0.0, 45.0, 5.0, "5m NE at equator"),
    (-27.0, -48.5, 0.0, 1.0, "1m North at -27° lat"),
    (-27.0, -48.5, 90.0, 5.0, "5m East at -27° lat"),
    # Drone-scale (10m - 100m)
    (0.0, 0.0, 90.0, 10.0, "10m East at equator"),
    (0.0, 0.0, 45.0, 50.0, "50m NE at equator"),
    (-27.0, -48.5, 30.0, 100.0, "100m at -27° lat, az=30°"),
    # Short (1km - 10km)
    (-22.9068, -43.1729, 225.0, 1000.0, "1km SW from Rio"),
    (-27.0, -48.5, 0.0, 5000.0, "5km North at -27° lat"),
    # Medium (50km - 500km)
    (-23.5505, -46.6333, 45.0, 100_000.0, "100km NE from São Paulo"),
    (-23.5505, -46.6333, 0.0, 500_000.0, "500km North from São Paulo"),
    # Long (1000km+)
    (0.0, 0.0, 90.0, 1_000_000.0, "1000km East along equator"),
    (40.7128, -74.006, 51.2, 5_570_000.0, "~5570km NYC→London azimuth"),
    # Polar region (max ellipsoid effect)
    (70.0, 0.0, 0.0, 100_000.0, "100km North from 70°N"),
]


def test_precision_with_exact_distances():
    print("PRECISION: Haversine vs Geodesic.Inverse against known distances")

    header = (
        f"\n{'Description':<40} {'Truth(m)':>12} "
        f"{'Geodesic(m)':>12} {'Geo Err':>10} "
        f"{'Haversine(m)':>13} {'Hav Err':>10} {'Hav Err%':>9}"
    )
    print(header)
    print("-" * 110)

    max_hav_pct = 0.0

    for lat1, lon1, az, true_dist, desc in EXACT_CASES:
        lat2, lon2 = _place_point(lat1, lon1, az, true_dist)

        geo_dist, _ = geodesic_inverse(lat1, lon1, lat2, lon2)
        hav_dist, _ = haversine_and_bearing(lat1, lon1, lat2, lon2)

        geo_err = abs(geo_dist - true_dist)
        hav_err = abs(hav_dist - true_dist)
        hav_pct = (hav_err / true_dist * 100) if true_dist > 0 else 0.0
        max_hav_pct = max(max_hav_pct, hav_pct)

        print(
            f"{desc:<40} {true_dist:>12.3f} "
            f"{geo_dist:>12.6f} {geo_err:>10.6f} "
            f"{hav_dist:>13.3f} {hav_err:>10.4f} {hav_pct:>8.4f}%"
        )

    print("-" * 110)
    print(f"Geodesic.Inverse round-trip error: always < 1e-5 m (sub-micrometer)")
    print(f"Haversine max error: {max_hav_pct:.4f}%")

    assert max_hav_pct < 0.6, f"Haversine error exceeded 0.6%: {max_hav_pct:.4f}%"


def test_bearing_precision():
    """Compare bearing accuracy against exact known azimuths."""
    print("\n" + "=" * 90)
    print("BEARING PRECISION: manual bearing vs Geodesic.Inverse azi1")
    print("=" * 90)

    header = (
        f"\n{'Description':<40} {'True Az(°)':>10} "
        f"{'Geodesic(°)':>11} {'Geo Err(°)':>11} "
        f"{'Haversine(°)':>12} {'Hav Err(°)':>11}"
    )
    print(header)
    print("-" * 98)

    for lat1, lon1, true_az, dist, desc in EXACT_CASES:
        lat2, lon2 = _place_point(lat1, lon1, true_az, dist)

        _, geo_brng = geodesic_inverse(lat1, lon1, lat2, lon2)
        _, hav_brng = haversine_and_bearing(lat1, lon1, lat2, lon2)

        true_az_norm = true_az % 360
        geo_err = abs(geo_brng - true_az_norm)
        if geo_err > 180:
            geo_err = 360 - geo_err
        hav_err = abs(hav_brng - true_az_norm)
        if hav_err > 180:
            hav_err = 360 - hav_err

        print(
            f"{desc:<40} {true_az_norm:>10.2f} "
            f"{geo_brng:>11.6f} {geo_err:>11.6f} "
            f"{hav_brng:>12.4f} {hav_err:>11.4f}"
        )


def test_drone_scale_errors():
    """(1m - 100m)"""

    drone_cases = [
        (-27.0, -48.5, 0.0, 1.0, "1m N"),
        (-27.0, -48.5, 90.0, 1.0, "1m E"),
        (-27.0, -48.5, 45.0, 2.0, "2m NE"),
        (-27.0, -48.5, 0.0, 5.0, "5m N"),
        (-27.0, -48.5, 90.0, 10.0, "10m E"),
        (-27.0, -48.5, 45.0, 20.0, "20m NE"),
        (-27.0, -48.5, 0.0, 50.0, "50m N"),
        (-27.0, -48.5, 90.0, 100.0, "100m E"),
    ]

    print(
        f"\n{'Desc':<10} {'Truth(m)':>10} {'Hav Err(cm)':>12} {'Hav Err%':>10} {'Geo Err(nm)':>12}"
    )
    print("-" * 58)

    for lat1, lon1, az, true_dist, desc in drone_cases:
        lat2, lon2 = _place_point(lat1, lon1, az, true_dist)
        geo_dist, _ = geodesic_inverse(lat1, lon1, lat2, lon2)
        hav_dist, _ = haversine_and_bearing(lat1, lon1, lat2, lon2)

        hav_err_cm = abs(hav_dist - true_dist) * 100
        hav_pct = abs(hav_dist - true_dist) / true_dist * 100
        geo_err_nm = abs(geo_dist - true_dist) * 1e9  # nanometers

        print(
            f"{desc:<10} {true_dist:>10.1f} {hav_err_cm:>12.4f} {hav_pct:>9.4f}% {geo_err_nm:>12.2f}"
        )

    lat2, lon2 = _place_point(-27.0, -48.5, 45.0, 100.0)
    hav_100 = GPSCalculate.haversine(-27.0, -48.5, lat2, lon2)
    assert (
        abs(hav_100 - 100.0) < 1.0
    ), f"Haversine 100m error > 1m: {abs(hav_100 - 100.0):.4f}m"


def test_timing_comparison():
    """Benchmark execution time at various distance scales."""
    print("\n" + "=" * 80)
    print("TIMING (mean over 10,000 iterations)")
    print("=" * 80)

    timing_cases = [
        ("1m", -27.0, -48.5, 0.0, 1.0),
        ("10m", -27.0, -48.5, 90.0, 10.0),
        ("100m", -27.0, -48.5, 45.0, 100.0),
        ("1km", -27.0, -48.5, 0.0, 1000.0),
        ("100km", -23.5505, -46.6333, 45.0, 100_000.0),
        ("5570km", 40.7128, -74.006, 51.2, 5_570_000.0),
    ]

    print(f"\n{'Scale':<10} {'Hav+Brng(µs)':>14} {'Geodesic(µs)':>14} {'Ratio':>8}")
    print("-" * 50)

    for name, lat1, lon1, az, dist in timing_cases:
        lat2, lon2 = _place_point(lat1, lon1, az, dist)
        t_hav = benchmark_timing(haversine_and_bearing, lat1, lon1, lat2, lon2)
        t_geo = benchmark_timing(geodesic_inverse, lat1, lon1, lat2, lon2)
        ratio = t_geo / t_hav if t_hav > 0 else float("inf")
        print(f"{name:<10} {t_hav:>14.2f} {t_geo:>14.2f} {ratio:>7.1f}x")

    print()


def test_geodesic_inverse_round_trip():
    """Verify Geodesic.Inverse perfectly recovers Direct-placed distances."""
    for lat1, lon1, az, true_dist, desc in EXACT_CASES:
        lat2, lon2 = _place_point(lat1, lon1, az, true_dist)
        result = Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2)
        error = abs(result["s12"] - true_dist)
        assert error < 1e-5, f"Round-trip error {error}m for {desc} (expected < 1e-5m)"


if __name__ == "__main__":
    test_precision_with_exact_distances()
    test_bearing_precision()
    test_drone_scale_errors()
    test_timing_comparison()
    test_geodesic_inverse_round_trip()
