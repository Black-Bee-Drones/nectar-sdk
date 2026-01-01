#!/usr/bin/env python3

from mirela_sdk.image_processing import (
    DistanceEstimator,
    DistanceCalibrator,
    EstimationMethod,
)


def basic_estimation_example():
    print("=== Basic Distance Estimation ===")

    estimator = DistanceEstimator(
        default_method=EstimationMethod.POLYNOMIAL,
        valid_range=(15.0, 35.0),
        validate_inputs=True,
    )

    test_measurements = [20.0, 25.0, 30.0]

    for pixel_measurement in test_measurements:
        distance = estimator.estimate(pixel_measurement)
        print(f"Pixel measurement: {pixel_measurement} -> Distance: {distance:.2f} cm")

    print(f"\nAvailable methods: {estimator.get_available_methods()}")


def calibration_example():
    print("\n=== Custom Calibration Example ===")

    calibrator = DistanceCalibrator()

    measurement_data = [
        (50, 32.2),
        (60, 28.5),
        (70, 24.2),
        (80, 23.9),
        (90, 23.0),
        (100, 21.6),
        (110, 20.1),
        (120, 19.9),
        (130, 18.1),
        (140, 17.2),
        (150, 16.8),
        (160, 16.0),
        (170, 15.0),
        (180, 14.8),
    ]

    print(f"Adding {len(measurement_data)} data points...")
    calibrator.add_data_points(measurement_data)

    linear_result = calibrator.calibrate_linear()
    print(f"\nLinear calibration:")
    print(f"  k = {linear_result['k']:.2f}")
    print(f"  RMSE = {linear_result['rmse']:.2f} cm")
    print(f"  R² = {linear_result['r2']:.4f}")

    poly_result = calibrator.calibrate_polynomial(degree=2)
    print(f"\nPolynomial (degree 2) calibration:")
    print(f"  RMSE = {poly_result['rmse']:.2f} cm")
    print(f"  R² = {poly_result['r2']:.4f}")

    best_name, best_params = calibrator.get_best_calibration()
    print(f"\nBest model: {best_name}")
    print(f"  RMSE = {best_params['rmse']:.2f} cm")
    print(f"  R² = {best_params['r2']:.4f}")

    custom_estimator = calibrator.create_estimator_from_calibration(
        valid_range=(15.0, 35.0)
    )

    test_pixel = 25.0
    estimated_distance = custom_estimator.estimate(test_pixel)
    print(f"\nUsing custom calibrated model:")
    print(f"  Pixel: {test_pixel} -> Distance: {estimated_distance:.2f} cm")


def method_comparison_example():
    print("\n=== Method Comparison ===")

    estimator = DistanceEstimator(validate_inputs=False)
    test_pixel = 25.0

    methods = [
        EstimationMethod.LINEAR,
        EstimationMethod.POLYNOMIAL,
        EstimationMethod.EXPONENTIAL,
        EstimationMethod.INVERSE_POWER,
        EstimationMethod.LOGARITHMIC,
        EstimationMethod.ROBUST_POLY2,
    ]

    print(f"Comparing methods for pixel measurement: {test_pixel}")
    print("-" * 50)

    for method in methods:
        try:
            distance = estimator.estimate(test_pixel, method)
            info = estimator.get_method_info(method)
            print(f"{info['name']:<25}: {distance:6.2f} cm")
        except Exception as e:
            print(f"{method.value:<25}: Error - {e}")


def validation_example():
    print("\n=== Input Validation Example ===")

    estimator = DistanceEstimator(
        default_method=EstimationMethod.POLYNOMIAL,
        valid_range=(15.0, 35.0),
        validate_inputs=True,
    )

    test_values = [10.0, 25.0, 40.0, -5.0, 0.0]

    for value in test_values:
        try:
            distance = estimator.estimate(value)
            print(f"Input: {value:5.1f} -> Distance: {distance:6.2f} cm")
        except Exception as e:
            print(f"Input: {value:5.1f} -> Error: {e}")


def real_world_scenario():
    print("\n=== Real-World Drone Landing Scenario ===")

    calibrator = DistanceCalibrator()

    hook_measurements = [
        (60, 28.5),
        (80, 23.9),
        (100, 21.6),
        (120, 19.9),
        (140, 17.2),
        (160, 16.0),
        (180, 14.8),
    ]

    calibrator.add_data_points(hook_measurements)

    linear_result = calibrator.calibrate_linear()
    poly_result = calibrator.calibrate_polynomial(degree=2)

    print("Drone hook detection calibration results:")
    print(
        f"Linear model RMSE: {linear_result['rmse']:.2f} cm (R²: {linear_result['r2']:.4f})"
    )
    print(
        f"Polynomial model RMSE: {poly_result['rmse']:.2f} cm (R²: {poly_result['r2']:.4f})"
    )

    estimator = calibrator.create_estimator_from_calibration(valid_range=(14.0, 30.0))

    print("\nLanding approach simulation:")
    detected_pixels = [30.0, 25.0, 22.0, 20.0, 18.0]
    target_distance = 80.0
    tolerance = 10.0

    for i, pixel in enumerate(detected_pixels):
        distance = estimator.estimate(pixel)
        status = (
            "✓ IN RANGE"
            if abs(distance - target_distance) <= tolerance
            else "✗ OUT OF RANGE"
        )
        print(f"Step {i+1}: Pixel={pixel:4.1f} -> Distance={distance:5.1f}cm {status}")


def generate_code_example():
    print("\n=== Code Generation Example ===")

    calibrator = DistanceCalibrator()

    sample_data = [
        (50, 32.2),
        (100, 21.6),
        (150, 16.8),
        (200, 13.5),
    ]

    calibrator.add_data_points(sample_data)
    calibrator.calibrate_linear()
    calibrator.calibrate_polynomial(degree=2)

    best_name, _ = calibrator.get_best_calibration()
    code = calibrator.generate_parameter_code(best_name)

    print(f"Generated code for {best_name} model:")
    print(code)


def main():
    print("🔬 Mirela SDK Distance Estimation Examples\n")

    basic_estimation_example()
    calibration_example()
    method_comparison_example()
    validation_example()
    real_world_scenario()
    generate_code_example()

    print("\n✨ All examples completed successfully!")


if __name__ == "__main__":
    main()
