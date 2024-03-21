from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "image_source",
                default_value="webcam",
                description="Source of the image",
            ),
            Node(
                package="mirela_sdk",
                executable="gesture_recognizer",
                name="gesture_recognizer",
                parameters=[{"image_source": LaunchConfiguration("image_source")}],
            ),
            Node(
                package="mirela_sdk",
                executable="gesture_controller",
                name="controller",
            ),
            Node(
                package="mirela_sdk",
                executable="gui",
                name="gui",
            ),
        ]
    )
