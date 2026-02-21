from typing import Any, Callable, Dict, Union

from rclpy.node import Node

from nectar.vision.camera.config import (
    C920Config,
    CameraConfig,
    FileImageConfig,
    IMX219Config,
    OakDConfig,
    OpenCVConfig,
    QoSDurability,
    QoSReliability,
    RealSenseConfig,
    ROSConfig,
    ROSDepthConfig,
)


def _get_param(params: Union[Node, Dict[str, Any]], key: str, default: Any = None) -> Any:
    """Extract parameter from Node or dict."""
    if isinstance(params, Node):
        return params.get_parameter(key).value
    return params.get(key, default)


ConfigBuilderFunc = Callable[[Union[Node, Dict[str, Any]]], CameraConfig]


class ConfigBuilder:
    """Registry for camera configuration builders."""

    _builders: Dict[str, ConfigBuilderFunc] = {}

    @classmethod
    def register(cls, key: str, builder: ConfigBuilderFunc) -> None:
        """Register config builder for camera type."""
        cls._builders[key.lower()] = builder

    @classmethod
    def is_registered(cls, source: str) -> bool:
        """Check if source is registered."""
        return source.lower() in cls._builders

    @classmethod
    def build(cls, source: str, params: Union[Node, Dict[str, Any]]) -> CameraConfig:
        """Build config from source key and parameters."""
        key = source.lower()
        builder = cls._builders.get(key)

        if not builder:
            return CameraConfig(name=source)

        return builder(params)


def _build_opencv_config(params: Union[Node, Dict[str, Any]]) -> OpenCVConfig:
    """Build OpenCVConfig from parameters."""
    return OpenCVConfig(
        name="camera",
        device_index=_get_param(params, "device_index", 0),
        width=_get_param(params, "width", 640),
        height=_get_param(params, "height", 480),
        fps=_get_param(params, "fps", 30),
        fourcc=_get_param(params, "fourcc", "MJPG"),
        autofocus=_get_param(params, "autofocus", None),
        focus=_get_param(params, "focus", None),
        buffer_size=min(max(_get_param(params, "buffer_size", 2), 1), 10),
        threaded=_get_param(params, "threaded", True),
    )


def _build_c920_config(params: Union[Node, Dict[str, Any]]) -> C920Config:
    """Build C920Config from parameters."""
    return C920Config(
        name="c920",
        profile=_get_param(params, "profile", 1),
        fallback_device_index=_get_param(params, "fallback_device_index", 0),
    )


def _build_imx219_config(params: Union[Node, Dict[str, Any]]) -> IMX219Config:
    """Build IMX219Config from parameters."""
    return IMX219Config(
        sensor_id=_get_param(params, "sensor_id", 0),
        width=_get_param(params, "width", 1920),
        height=_get_param(params, "height", 1080),
        fps=_get_param(params, "fps", 30),
        flip=_get_param(params, "flip", 0),
        brightness=_get_param(params, "brightness", None),
    )


def _build_realsense_config(params: Union[Node, Dict[str, Any]]) -> RealSenseConfig:
    """Build RealSenseConfig from parameters."""
    return RealSenseConfig(
        color_res=(
            _get_param(params, "color_width", 640),
            _get_param(params, "color_height", 480),
        ),
        depth_res=(
            _get_param(params, "depth_width", 640),
            _get_param(params, "depth_height", 480),
        ),
        fps=_get_param(params, "fps", 30),
        align_to_color=_get_param(params, "align_to_color", True),
        enable_depth=_get_param(params, "enable_depth", True),
        use_ros_topics=_get_param(params, "use_ros_topics", False),
        color_topic=_get_param(params, "color_topic", "/camera/color/image_raw"),
        depth_topic=_get_param(params, "depth_topic", "/camera/depth/image_rect_raw"),
        color_compressed=_get_param(params, "color_compressed", True),
        depth_compressed=_get_param(params, "depth_compressed", False),
    )


def _build_oakd_config(params: Union[Node, Dict[str, Any]]) -> OakDConfig:
    """Build OakDConfig from parameters."""
    return OakDConfig(
        cam_num=_get_param(params, "cam_num", 1),
        enable_depth=_get_param(params, "enable_depth", False),
    )


def _build_ros_config(params: Union[Node, Dict[str, Any]]) -> ROSConfig:
    """Build ROSConfig from parameters."""
    reliability_str = _get_param(params, "reliability", "best_effort")
    durability_str = _get_param(params, "durability", "volatile")

    return ROSConfig(
        topic=_get_param(params, "topic", "/image_raw"),
        compressed=_get_param(params, "compressed", False),
        reliability=QoSReliability(reliability_str),
        durability=QoSDurability(durability_str),
        history_depth=_get_param(params, "history_depth", 1),
        encoding=_get_param(params, "encoding", "bgr8"),
    )


def _build_ros_depth_config(params: Union[Node, Dict[str, Any]]) -> ROSDepthConfig:
    """Build ROSDepthConfig from parameters."""
    reliability_str = _get_param(params, "reliability", "best_effort")
    durability_str = _get_param(params, "durability", "volatile")

    return ROSDepthConfig(
        topic=_get_param(params, "topic", "/image_raw"),
        compressed=_get_param(params, "compressed", False),
        reliability=QoSReliability(reliability_str),
        durability=QoSDurability(durability_str),
        history_depth=_get_param(params, "history_depth", 1),
        encoding=_get_param(params, "encoding", "bgr8"),
        depth_topic=_get_param(params, "depth_topic", "/camera/depth/image_rect_raw"),
        depth_compressed=_get_param(params, "depth_compressed", False),
        depth_encoding=_get_param(params, "depth_encoding", "passthrough"),
        enable_depth=_get_param(params, "enable_depth", True),
    )


def _build_file_config(params: Union[Node, Dict[str, Any]]) -> FileImageConfig:
    """Build FileImageConfig from parameters."""
    return FileImageConfig(
        path=_get_param(params, "file_path", ""),
    )


ConfigBuilder.register("webcam", _build_opencv_config)
ConfigBuilder.register("opencv", _build_opencv_config)
ConfigBuilder.register("c920", _build_c920_config)
ConfigBuilder.register("imx219", _build_imx219_config)
ConfigBuilder.register("realsense", _build_realsense_config)
ConfigBuilder.register("oakd", _build_oakd_config)
ConfigBuilder.register("ros", _build_ros_config)
ConfigBuilder.register("ros_depth", _build_ros_depth_config)
ConfigBuilder.register("file", _build_file_config)
