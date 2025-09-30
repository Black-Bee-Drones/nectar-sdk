#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from time import sleep
import threading
from collections import defaultdict

from mirela_sdk.control.mavros.mavros_api import MavDrone


class TestGPS(Node):
    def __init__(self):
        super().__init__("test_gps")
        self.get_logger().info("Initializing GPS test node...")

        self.drone = MavDrone(node=self, mavros=False)
        self.drone.check_driver_node()

        self.msg_counters = defaultdict(int)
        self.running = True

        self.monitor_thread = threading.Thread(target=self.monitor_gps_data)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        self.get_logger().info("GPS test node has been initialized")

    def monitor_gps_data(self):
        """Thread function to continually spin and count GPS messages"""
        while self.running:
            rclpy.spin_once(self, timeout_sec=0.1)

            self.msg_counters["gps_msgs"] += 1

            if self.msg_counters["gps_msgs"] % 10 == 0:
                self.log_gps_data()

            sleep(0.1)

    def log_gps_data(self):
        """Log the current GPS data values"""
        gps_data = self.drone.get_gps
        rel_alt = self.drone.get_rel_alt
        rng_alt = self.drone.get_rng_alt
        heading = self.drone.get_heading

        self.get_logger().info(
            f"--- GPS Data (Message #{self.msg_counters['gps_msgs']}) ---"
        )
        self.get_logger().info(f"Latitude: {gps_data.latitude}")
        self.get_logger().info(f"Longitude: {gps_data.longitude}")
        self.get_logger().info(f"Altitude: {gps_data.altitude}")
        self.get_logger().info(f"Status: {gps_data.status.status}")
        self.get_logger().info(f"Relative Altitude: {rel_alt.data}")
        self.get_logger().info(f"Rangefinder Altitude: {rng_alt.range}")
        self.get_logger().info(f"Heading: {heading.data}")
        self.get_logger().info("-----------------------------")

    def run(self):
        """Run the main test sequence"""
        self.get_logger().info("Starting GPS data collection...")

        sleep_time = 30
        self.get_logger().info(f"Collecting GPS data for {sleep_time} seconds...")

        sleep(sleep_time)

        self.get_logger().info("GPS data collection complete")

        self.get_logger().info("\n=== GPS Data Collection Summary ===")
        self.get_logger().info(
            f"Total GPS messages processed: {self.msg_counters['gps_msgs']}"
        )

        self.get_logger().info("\n=== Final GPS Data ===")
        self.log_gps_data()

        # Check if we received valid GPS data
        gps_data = self.drone.get_gps
        if gps_data.latitude == 0.0 and gps_data.longitude == 0.0:
            self.get_logger().warn(
                "No valid GPS data received! Check if hardware is connected properly."
            )
        else:
            self.get_logger().info("Valid GPS data received!")

    def shutdown(self):
        """Clean shutdown of the node"""
        self.running = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        self.get_logger().info("GPS test node shut down")


def main(args=None):
    rclpy.init(args=args)

    test_gps = TestGPS()

    try:
        test_gps.run()

        rclpy.spin(test_gps)
    except KeyboardInterrupt:
        pass
    finally:
        test_gps.shutdown()
        test_gps.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
