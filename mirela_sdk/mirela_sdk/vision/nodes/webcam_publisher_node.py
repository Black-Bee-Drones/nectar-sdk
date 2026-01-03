#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2
import os
import threading
import queue
import time
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy


class WebcamPublisher(Node):
    """
    High-performance webcam publisher with low-latency optimizations.
    """

    def __init__(self):
        super().__init__("webcam_publisher")

        self.declare_parameter("fps", 30)
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("buffer_size", 1)
        self.declare_parameter("use_compression", True)
        self.declare_parameter("jpeg_quality", 80)
        self.declare_parameter("use_threading", True)
        self.declare_parameter("camera_index", 0)

        # Get parameters
        self.fps = self.get_parameter("fps").get_parameter_value().integer_value
        self.width = self.get_parameter("width").get_parameter_value().integer_value
        self.height = self.get_parameter("height").get_parameter_value().integer_value
        self.buffer_size = (
            self.get_parameter("buffer_size").get_parameter_value().integer_value
        )
        self.use_compression = (
            self.get_parameter("use_compression").get_parameter_value().bool_value
        )
        self.jpeg_quality = (
            self.get_parameter("jpeg_quality").get_parameter_value().integer_value
        )
        self.use_threading = (
            self.get_parameter("use_threading").get_parameter_value().bool_value
        )
        self.camera_index = (
            self.get_parameter("camera_index").get_parameter_value().integer_value
        )

        # Configure QoS for low latency
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,  
            history=HistoryPolicy.KEEP_LAST,
            depth=1,  
            durability=DurabilityPolicy.VOLATILE,
        )

        # Create publishers
        if self.use_compression:
            self.publisher_ = self.create_publisher(
                CompressedImage, "image_raw/compressed", qos_profile
            )
        else:
            self.publisher_ = self.create_publisher(Image, "image_raw", qos_profile)

        self.bridge = CvBridge()

        self.cap = self._initialize_camera()

        if self.cap is None:
            self.get_logger().error("Failed to initialize camera")
            rclpy.shutdown()
            return

        # Threading setup
        if self.use_threading:
            self.frame_queue = queue.Queue(maxsize=2)  # Small buffer to try reduce latency
            self.capture_thread = threading.Thread(
                target=self._capture_frames, daemon=True
            )
            self.capture_thread.start()

            timer_period = 1.0 / self.fps
            self.timer = self.create_timer(timer_period, self._publish_frame_threaded)
        else:
            # Single-threaded mode
            timer_period = 1.0 / self.fps
            self.timer = self.create_timer(timer_period, self._publish_frame_direct)

        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps_counter = 0

        self.jpeg_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]

        self.get_logger().info(
            f"Optimized Webcam Publisher started - FPS: {self.fps}, "
            f"Resolution: {self.width}x{self.height}, "
            f"Compression: {self.use_compression}, "
            f"Threading: {self.use_threading}"
        )

    def _initialize_camera(self):
        # Try different camera indices
        camera_indices_to_try = [self.camera_index, 0, 1, 2]
        cap = None

        for index in camera_indices_to_try:
            if os.path.exists(f"/dev/video{index}"):
                cap = cv2.VideoCapture(
                    index, cv2.CAP_V4L2
                )  # Use V4L2 backend 

                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    cap.set(cv2.CAP_PROP_FPS, self.fps)
                    cap.set(
                        cv2.CAP_PROP_BUFFERSIZE, self.buffer_size
                    )  # Minimize buffer

                    cap.set(
                        cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G")
                    )  # MJPEG for better performance
                    cap.set(
                        cv2.CAP_PROP_AUTO_EXPOSURE, 0.25
                    )  # Disable auto exposure for consistent timing

                    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)

                    self.get_logger().info(
                        f"Camera {index} initialized - "
                        f"Resolution: {actual_width}x{actual_height}, "
                        f"FPS: {actual_fps}"
                    )
                    return cap
                else:
                    if cap:
                        cap.release()

        return None

    def _capture_frames(self):
        """Continuous frame capture in separate thread."""
        while rclpy.ok() and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Clear old frames to maintain low latency
                try:
                    while not self.frame_queue.empty():
                        self.frame_queue.get_nowait()
                except queue.Empty:
                    pass

                # Add new frame
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    pass  # Drop frame if queue is full
            else:
                time.sleep(0.001)  # Small delay on capture failure

    def _publish_frame_threaded(self):
        """Publish frame from queue (threaded mode)."""
        try:
            frame = self.frame_queue.get_nowait()
            self._process_and_publish_frame(frame)
        except queue.Empty:
            # No frame available, skip this cycle
            pass

    def _publish_frame_direct(self):
        """Capture and publish frame directly (single-threaded mode)."""
        if self.cap is None or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if ret:
            self._process_and_publish_frame(frame)

    def _process_and_publish_frame(self, frame):
        """Process and publish a frame with optimizations."""
        try:
            current_time = self.get_clock().now().to_msg()

            if self.use_compression:
                # Compress image 
                _, compressed_data = cv2.imencode(".jpg", frame, self.jpeg_params)

                # Create compressed image message
                compressed_msg = CompressedImage()
                compressed_msg.header.stamp = current_time
                compressed_msg.header.frame_id = "camera_frame"
                compressed_msg.format = "jpeg"
                compressed_msg.data = compressed_data.tobytes()

                self.publisher_.publish(compressed_msg)
            else:
                # Publish uncompressed image
                ros_image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
                ros_image.header.stamp = current_time
                ros_image.header.frame_id = "camera_frame"
                self.publisher_.publish(ros_image)

            # Performance monitoring
            self._update_fps_counter()

        except Exception as e:
            self.get_logger().warn(f"Error processing frame: {e}")

    def _update_fps_counter(self):
        """Monitor actual FPS performance."""
        self.fps_counter += 1
        current_time = time.time()

        if current_time - self.last_fps_time >= 5.0:  # Report every 5 seconds
            actual_fps = self.fps_counter / (current_time - self.last_fps_time)
            self.get_logger().info(f"Actual FPS: {actual_fps:.1f}")
            self.fps_counter = 0
            self.last_fps_time = current_time

    def destroy_node(self):
        """Cleanup resources."""
        self.get_logger().info("Shutting down Optimized Webcam Publisher node.")

        if hasattr(self, "capture_thread") and self.capture_thread.is_alive():
            # Signal thread to stop and wait
            self.capture_thread.join(timeout=1.0)

        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.get_logger().info("Camera released.")

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        webcam_publisher = WebcamPublisher()
        rclpy.spin(webcam_publisher)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:
        if "webcam_publisher" in locals():
            webcam_publisher.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
