from abc import ABC, abstractmethod
from time import sleep

from rclpy.qos import QoSProfile
from rclpy.node import Node
from rclpy.publisher import Publisher
from rclpy.subscription import Subscription
from rclpy.client import Client


class Drone(ABC):
    """
    Abstract base class for controlling drones using ROS2.

    This class defines common attributes and methods that can be inherited
    by concrete drone classes (e.g., MavDrone and Bebop).
    """

    def __init__(self, node: Node) -> None:
        self.node = node

        # ROS2 objects (to be populated by subclasses)
        self._subscribers = []
        self._clients = []
        self._publishers = []

        # Common drone state variables
        self._is_flying = False
        self._driver_initialized = False

    @property
    def subscribers(self) -> list[Subscription]:
        """
        Get the list of subscribers initialized by class
        """
        return self._subscribers

    @property
    def clients(self) -> list[Client]:
        """
        Get the list of clients initialized by class
        """
        return self._clients

    @property
    def publishers(self) -> list[Publisher]:
        """
        Get the list of publishers initialized by class
        """
        return self._publishers

    @property
    def is_flying(self) -> bool:
        """
        Get the flying state of the drone.
        """
        return self._is_flying

    @property
    def driver_initialized(self) -> bool:
        """
        Get the driver initialization state of the drone.
        """
        return self._driver_initialized

    def cleanup(self) -> None:
        """
        Clean up ROS2 objects associated with the drone.
        """
        for subscriber in self._subscribers:
            self.node.destroy_subscription(subscriber)

        for publisher in self._publishers:
            self.node.destroy_publisher(publisher)

        for client in self._clients:
            self.node.destroy_client(client)

    @abstractmethod
    def init_drivers(self) -> None:
        """
        Initialize the drivers for the drone (implementation specific).
        """
        raise NotImplementedError("init_drivers() must be implemented by a subclass")

    @abstractmethod
    def check_driver_node(self) -> bool:
        """
        Check if node of corresponding driver is running
        """
        raise NotImplementedError(
            "check_driver_node() must be implemented by a subclass"
        )

    @abstractmethod
    def takeoff(self) -> None:
        """
        Send a takeoff command to the drone (implementation specific).
        """
        raise NotImplementedError("takeoff() must be implemented by a subclass")

    @abstractmethod
    def land(self) -> None:
        """
        Send a land command to the drone (implementation specific).
        """
        raise NotImplementedError("land() must be implemented by a subclass")

    @abstractmethod
    def image_viewer(self) -> None:
        """
        Display images from the drone's camera.
        """
        raise NotImplementedError("image_viewer() must be implemented by a subclass")

    @abstractmethod
    def record(self, record: bool) -> None:
        """
        Start or stop recording video.
        """
        raise NotImplementedError("record() must be implemented by a subclass")

    @abstractmethod
    def snapshot(self) -> None:
        """
        Take a snapshot.
        """
        raise NotImplementedError("snapshot() must be implemented by a subclass")

    def delay(self, time: float) -> None:
        """
        Delay the execution of the program.
        """

        self.node.get_logger().info(f"-- Init delay {time}")
        sleep(time)
        self.node.get_logger().info(f"-- End delay {time}")

    def _create_subscriber(
        self, msg_type: type, topic: str, callback: callable, qos: QoSProfile
    ) -> Subscription:
        """
        Helper function to create a ROS2 subscriber with common configuration.

        :param msg_type (str): ROS2 message type.
        :param topic (str): ROS2 topic name.
        :param callback (callable): Callback function for incoming messages.
        :param qos (QoSProfile): ROS2 Quality of Service profile.
        """
        subscriber = self.node.create_subscription(msg_type, topic, callback, qos)
        self._subscribers.append(subscriber)
        return subscriber

    def _create_client(self, srv_type, service_name: str) -> Client:
        """
        Helper function to create a ROS2 service client.

        :param srv_type: ROS2 service type.
        :param service_name (str): ROS2 service name.
        """
        client = self.node.create_client(srv_type, service_name)
        self._clients.append(client)
        return client

    def _create_publisher(
        self, msg_type: type, topic: str, qos: QoSProfile
    ) -> Publisher:
        """
        Helper function to create a ROS2 publisher with common configuration.

        :param msg_type: ROS2 message type.
        :param topic (str): ROS2 topic name.
        :param qos (QoSProfile): ROS2 Quality of Service profile.
        """
        publisher = self.node.create_publisher(msg_type, topic, qos)
        self._publishers.append(publisher)
        return publisher
