import depthai as dai
import cv2

from typing import Optional, Tuple
from enum import Enum

import json
from pathlib import Path
import numpy as np

from mirela_sdk.vision.camera.abstract import DepthCam
from mirela_sdk.vision.camera.config import OakDConfig


class OakdCameraResolution(Enum):
    """
    Enum class to color camera resolution types.

    """

    THE_540_P = "THE_540_P"
    THE_1080_P = dai.ColorCameraProperties.SensorResolution.THE_1080_P
    THE_4K = dai.ColorCameraProperties.SensorResolution.THE_4_K


class PipelineOrderingError(Exception): ...


class OakdCam(DepthCam):
    """
    Class to initialize the pipeline and define the parameters for accessing OAKD images

    Note: all pipeline links must be configured before starting it. Some ready settings in this
    class prevent it, but for standalone applications you must pay attention to this.

    """

    # TODO: Enum for the following attributes:

    RGB = "rgb"
    LEFT = "left"
    RIGHT = "right"
    AUTOEXPOSURE = "autoexposure"
    ANTI_BANDING_MODE = "anti_banding_mode"
    AWB_MODE = "awb_mode"
    EFFECT_MODE = "effect_mode"
    AUTOFOCUS = "autofocus"
    AE_COMP = "ae_comp"
    BRIGHTNESS = "brightness"
    CONTRAST = "contrast"
    SATURATION = "saturation"
    SHARPNESS = "sharpness"
    LUMA_DENOISE = "luma_denoise"
    CHROMA_DENOISE = "chroma_denoise"
    EXPOSURE_TIME = "exposure_time"
    SENSITIVITY_ISO = "sensitivity_iso"
    FOCUS = "focus"
    WHITE_BALANCE = "white_balance"

    def __init__(self, config=None) -> None:
        """
        OakdCam constructor: initializes the pipeline and configures cameras with their
        board sockets

        :param config: OakDConfig instance with camera configuration
        """

        super().__init__("oakd")

        self.pipeline = dai.Pipeline()
        self.oak_dict = {
            1: (OakdCam.RGB, dai.CameraBoardSocket.CAM_A),
            2: (OakdCam.LEFT, dai.CameraBoardSocket.CAM_B),
            3: (OakdCam.RIGHT, dai.CameraBoardSocket.CAM_C),
        }
        self.device = None
        self.camera_resolution = OakdCameraResolution.THE_540_P

        self._config = config if config is not None else OakDConfig()

        self.spatial_calc_config = None
        self.spatial_calc_config_inqueue = None

        # For DepthCam-style usage
        self.__cam_num: int = self._config.cam_num
        self.__link_out: bool = True
        self.__have_depth: bool = self._config.enable_depth
        self.__rgb_queue = None
        self.__depth_queue = None

    # DepthCam-style API
    def start(
        self,
        cam_num: int = None,
        *,
        usb2mode=False,
        enable_depth: bool = False,
        camera_resolution: OakdCameraResolution = OakdCameraResolution.THE_540_P,
        set_control: bool = True,
    ) -> None:

        # Use config values if parameters not provided
        if cam_num is None:
            cam_num = self.__cam_num
        if enable_depth is None:
            enable_depth = self.__have_depth

        # Configure the color camera (keeps internal cam_type as RGB)
        self.camera_resolution = camera_resolution
        self.setup_camera(cam_num, link_out=True, set_control=set_control)

        if enable_depth:
            self.depth_config()
            self.__have_depth = True
        else:
            self.__have_depth = False

        self.init_cam(usb2mode)
        # Get queues explicitly by stream name to avoid relying on cam_type
        self.__rgb_queue = self.getQueue(OakdCam.RGB, maxSize=1, blocking=False)
        if self.__have_depth:
            self.__depth_queue = self.getQueue("depth", maxSize=4, blocking=False)

        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:

        if self.__rgb_queue is None:
            return None
        try:
            msg = self.__rgb_queue.get()
            if msg is None:
                return None
            return msg.getCvFrame()
        except Exception:
            return None

    def get_depth_frame(self) -> Optional[np.ndarray]:

        if not self.__have_depth or self.__depth_queue is None:
            return None
        try:
            depth_mm = self.getFrame(self.__depth_queue)
        except Exception:
            return None
        if depth_mm is None:
            return None

        # Convert millimeters to meters (float32)
        if depth_mm.dtype != np.float32:
            depth_m = depth_mm.astype(np.float32) / 1000.0
        else:
            depth_m = depth_mm
        return depth_m

    def get_distance(self, u: int, v: int) -> Optional[float]:

        depth = self.get_depth_frame()
        if depth is None:
            return None
        h, w = depth.shape[:2]
        if not (0 <= v < h and 0 <= u < w):
            return None
        return float(depth[int(v), int(u)])

    def close(self) -> None:

        try:
            if self.device is not None:
                self.device.close()
        except Exception:
            ...

        self.device = None
        self.__rgb_queue = None
        self.__depth_queue = None
        self._is_running = False

    @property
    def camera_resolution(self) -> OakdCameraResolution:
        return self.__camera_resolution

    @camera_resolution.setter
    def camera_resolution(self, cam_resolution: OakdCameraResolution) -> None:
        """
        Setter for the Color Camera resolution. This property has to be set before setup
        camera to take effect.

        :param cam_resolution (OakdCameraResolution): the resolution for the color camera.

        Note: for 540P resolution, the resolution is set to 1080P and ISP scale to (1,2).

        """

        if not isinstance(cam_resolution, OakdCameraResolution):
            raise TypeError(
                "camera resolution type is invalid. Use OakdCameraResolution types"
            )

        self.__camera_resolution = cam_resolution

    def setup_camera(
        self, cam_num: int, link_out: bool = True, set_control: bool = True
    ) -> dai.node.ColorCamera | dai.node.MonoCamera | None:
        """
        Function to set the camera type based on the camera number parameter

        :param cam_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam,
         3 for right monochrome cam
        :param link_out (bool): link the camera output with xout input,
         False to wait for another application
        :param set_control (bool): True for set initial control settings. False for otherwise
        """

        self.__link_out = link_out
        self.__cam_num = cam_num
        self.cam_type, self.boardSocket = self.oak_dict.get(
            self.__cam_num, ("invalid", None)
        )

        camera = None

        if self.cam_type != "invalid":

            if self.cam_type == OakdCam.RGB:
                camera = self.color_camera()
                if set_control:
                    self.__set_control_input(camera)
                    self.__oakd_controls()

            else:
                camera = self.mono_camera()

        else:
            raise ValueError("Invalid value for cam_num")

        return camera

    def init_cam(self, usb2_mode: bool = False) -> dai.Device:
        """
        Initialize the device and return it
        """

        self.device = dai.Device(self.pipeline, usb2Mode=usb2_mode)

        return self.device

    def color_camera(self) -> dai.node.ColorCamera:
        """
        Link device to host, set resolution, Isp scale and fps to get the color camera
        """

        cam = self.pipeline.createColorCamera()
        cam.setBoardSocket(self.boardSocket)
        isp_scale, cam_resolution = (
            ((1, 1), self.camera_resolution)
            if self.camera_resolution != OakdCameraResolution.THE_540_P
            else ((1, 2), OakdCameraResolution.THE_1080_P)
        )

        cam.setResolution(cam_resolution.value)
        cam.setIspScale(isp_scale[0], isp_scale[1])

        # Create communication link between camera and host(pc)
        xOut_rgb = self.pipeline.createXLinkOut()
        xOut_rgb.setStreamName(OakdCam.RGB)

        # Camera as input of communication link:
        cam.isp.link(xOut_rgb.input)

        return cam

    def mono_camera(self) -> dai.node.MonoCamera:
        """
        Link device and host to get the mono cameras
        """

        cam = self.pipeline.createMonoCamera()
        cam.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        cam.setBoardSocket(self.boardSocket)
        xout = self.pipeline.createXLinkOut()
        xout.setStreamName(self.cam_type)

        if self.__link_out:
            cam.out.link(xout.input)

        return cam

    def getQueue_CamType(self) -> dai.DataOutputQueue:
        """
        Gets an output queue corresponding to cam_type. If it doesn't exist it throws.
            Use this function to get the output queue from cam_type defined in the "setup()" scope
        """

        return self.device.getOutputQueue(self.cam_type, maxSize=1, blocking=False)

    def getQueue(
        self, stream_name: str, maxSize: int, blocking: bool = True
    ) -> dai.DataOutputQueue:
        """
        Gets an output queue corresponding to stream name. If it doesn't exist it throws

        :param stream_name (str): the stream name for output queue
        :param maxSize (int): max size of the queue
        :param blocking (bool): True for block the return of the function until
         arrive new msgs in the queue. False for otherwise
        """

        return self.device.getOutputQueue(stream_name, maxSize, blocking=blocking)

    def getFrame(self, queue: dai.DataOutputQueue) -> cv2.Mat:
        """
        Gets the cv frame from output queue frame wich is depthai.ImgFrame

        :param queue (dai.DataOutputQueue): the output queue from getQueue function
        """

        return queue.get().getCvFrame()

    def get_stereo_depth(self) -> dai.node.StereoDepth:
        """
        Set stereo settings and get it to use.
        """

        stereo = self.pipeline.createStereoDepth()

        # Better handling for occlusions:
        stereo.setLeftRightCheck(True)

        # Closer-in minimum depth, disparity range is doubled (from 95 to 190):
        stereo.setExtendedDisparity(False)

        # Better accuracy for longer distance, fractional disparity 32-levels:
        stereo.setSubpixel(False)

        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)

        # Options: MEDIAN_OFF, KERNEL_3x3, KERNEL_5x5, KERNEL_7x7 (default)
        stereo.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)

        self.stereo_links = {
            "disparity": stereo.disparity.link,
            "depth": stereo.depth.link,
            "rectifiedLeft": stereo.rectifiedLeft.link,
            "rectifiedRight": stereo.rectifiedRight.link,
            "syncedLeft": stereo.syncedLeft.link,
            "syncedRight": stereo.syncedRight.link,
        }

        # Create mono cameras directly without changing self.cam_type
        mono_left = self.pipeline.createMonoCamera()
        mono_left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
        mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        mono_right = self.pipeline.createMonoCamera()
        mono_right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
        mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        stereo.setOutputSize(
            mono_left.getResolutionWidth(), mono_left.getResolutionHeight()
        )

        mono_left.out.link(stereo.left)
        mono_right.out.link(stereo.right)

        return stereo

    def post_processing_stereo_depth(self, stereo: dai.node.StereoDepth) -> None:
        """
        Function to apply depth post-processing settings to the final map

        -----------
        https://docs.luxonis.com/software/depthai/examples/depth_post_processing/
        """

        config = stereo.initialConfig.get()
        config.postProcessing.speckleFilter.enable = False
        config.postProcessing.speckleFilter.speckleRange = 50
        config.postProcessing.temporalFilter.enable = True
        config.postProcessing.spatialFilter.enable = True
        config.postProcessing.spatialFilter.holeFillingRadius = 2
        config.postProcessing.spatialFilter.numIterations = 1
        config.postProcessing.thresholdFilter.minRange = 400
        config.postProcessing.thresholdFilter.maxRange = 15000
        config.postProcessing.decimationFilter.decimationFactor = 1
        stereo.initialConfig.set(config)

    def configure_stereo_node_output(self, stream_names: list[str]) -> None:
        """
        Set the stereo output requested

        :param stream_names list[str]: stream names to configure
        ("disparity", "depth", "rectifiedLeft", "rectifiedRight", "syncedLeft", "syncedRight")
        """

        if not isinstance(stream_names, list):
            raise TypeError(
                "Invalid type for stream name. It must be a list of strings"
            )

        for stream_name in stream_names:

            link = self.stereo_links.get(stream_name, None)

            if link:

                xout = self.pipeline.createXLinkOut()
                xout.setStreamName(stream_name)
                link(xout.input)

            else:
                raise ValueError("Invalid stream name value")

    def create_imu(self) -> dai.node.IMU:
        """
        Create an IMU sensor and return it.

        Note: OAK-D-LITE doesn't have IMU
        """

        self.imu = self.pipeline.createIMU()
        xout = self.pipeline.createXLinkOut()
        xout.setStreamName("imu")

        self.imu_sensors = {
            "accelerometer": dai.IMUSensor.ACCELEROMETER,
            "gyroscope": dai.IMUSensor.GYROSCOPE_RAW,
        }

        self.imu.out.link(xout.input)

        return self.imu

    def enable_imu_sensor(self, sensor_name: str, rate: int) -> None:
        """
        Enable the IMU sensor requested

        :param sensor_name (str): the sensor name to enable ("accelerometer", "gyroscope")
        :param rate (int): the measurement frequency, in Hz, of the sensor. Max frequencies:
         accelerometer -> 512 Hz, gyroscope -> 1000 Hz
        """

        sensor = self.imu_sensors.get(sensor_name, None)

        if sensor:

            self.imu.enableIMUSensor(sensor, rate)

        else:
            raise ValueError("Invalid sensor name value")

    def __set_control_input(self, cam: dai.node.ColorCamera) -> None:
        """
        Set the input control link to control the camera settings

        :param cam (dai.node.ColorCamera): the camera to link the input control
        """

        control_input_link = self.pipeline.createXLinkIn()
        control_input_link.setStreamName("control")

        control_input_link.out.link(cam.inputControl)

    def __oakd_controls(self) -> None:
        """
        Set the camera control and the control functions dictionary
        """

        self.ctrl = dai.CameraControl()
        self.__controls = {
            OakdCam.AUTOEXPOSURE: self.ctrl.setAutoExposureEnable,
            OakdCam.ANTI_BANDING_MODE: self.ctrl.setAntiBandingMode,
            OakdCam.AWB_MODE: self.ctrl.setAutoWhiteBalanceMode,
            OakdCam.EFFECT_MODE: self.ctrl.setEffectMode,
            OakdCam.AUTOFOCUS: self.ctrl.setAutoFocusMode,
            OakdCam.AE_COMP: self.ctrl.setAutoExposureCompensation,
            OakdCam.BRIGHTNESS: self.ctrl.setBrightness,
            OakdCam.CONTRAST: self.ctrl.setContrast,
            OakdCam.SATURATION: self.ctrl.setSaturation,
            OakdCam.SHARPNESS: self.ctrl.setSharpness,
            OakdCam.LUMA_DENOISE: self.ctrl.setLumaDenoise,
            OakdCam.CHROMA_DENOISE: self.ctrl.setChromaDenoise,
        }

        self.__manual_controls = {
            OakdCam.EXPOSURE_TIME: self.ctrl.setManualExposure,
            OakdCam.SENSITIVITY_ISO: self.ctrl.setManualExposure,
            OakdCam.FOCUS: self.ctrl.setManualFocus,
            OakdCam.WHITE_BALANCE: self.ctrl.setManualWhiteBalance,
        }

        self.__range_control = [
            "brightness",
            "contrast",
            "saturation",
            "ae_comp",
            "sharpness",
            "luma_denoise",
            "chroma_denoise",
        ]

        self.__expTime = 20000
        self.__sensIso = 800

        self.awb_modes = {
            name: mode
            for name, mode in vars(self.ctrl.AutoWhiteBalanceMode).items()
            if name.isupper()
        }
        self.antband_modes = {
            name: mode
            for name, mode in vars(self.ctrl.AntiBandingMode).items()
            if name.isupper()
        }
        self.effect_modes = {
            name: mode
            for name, mode in vars(self.ctrl.EffectMode).items()
            if name.isupper()
        }
        self.aut_foc_modes = {
            name: mode
            for name, mode in vars(self.ctrl.AutoFocusMode).items()
            if name.isupper()
        }

        self.__control_modes = [
            OakdCam.AWB_MODE,
            OakdCam.ANTI_BANDING_MODE,
            OakdCam.EFFECT_MODE,
            OakdCam.AUTOFOCUS,
        ]

    def __enable_binary_controls(
        self, control: str, action: callable, mode=None
    ) -> str:
        """
        Enable binaries control parameters or set the parameters wich need a mode.

        :param control (str): Name of the control to call the function.
        :param action (callable): the function to be call for set the changes.
        :param mode (control_mode): The mode connected to control passed (from dai.CameraControl..)

         Return the result of the set operation as str
        """

        if control == "autoexposure":
            action()
            return "Autoexposure enabled"

        elif control in self.__control_modes:
            action(mode)
            return f"{control.capitalize()}: {mode}"

    def __put_in_range(self, control: str, value: int) -> int:
        """
        Check if the value is within the range according the control parameter. If not, return max
         or min from range

        :param control (str): the control name to check the correct range.
        :param value (int): the value to check if it is within the range.
        """

        match (control):
            case "ae_comp":
                return max(-9, min(9, value))
            case "brightness" | "contrast" | "saturation":
                return max(-10, min(10, value))
            case "sensitivity_iso":
                return max(100, min(1600, value))
            case "exposure_time":
                return max(1, min(33000, value))
            case "focus":
                return max(0, min(255, value))
            case "white_balance":
                return max(1000, min(12000, value))
            case _:
                return max(0, min(4, value))

    def get_control_input_queue(self) -> dai.DataInputQueue:
        """
        Get the input control queue
        """

        return self.device.getInputQueue("control")

    def set_control(self, control: str, value: int = 0, mode=None) -> str:
        """
        Set the variable control for OAK-D

        :param control (str): the control to change the value ( brightness | contrast | saturation
         | sharpness | luma_denoise | chroma_denoise | ae_comp | autoexposure | anti_banding_mode |
         awb_mode | effect_mode | autofocus )
        :param value (int): the integer value to set the control. Range -10 .. +10 for brightness,
         contrast and saturation. For sharpness, luma denoise and chroma denoise the range is 0 .. +4
         For ae_comp -9 .. +9. Use this parameter if the control parameter needs an integer value.
        :param mode (control_mode): The mode connected to control passed (from dai.CameraControl..)

         Return the result as a string
        """

        action = self.__controls.get(control, None)

        if action:

            if control in self.__range_control:

                value = self.__put_in_range(control, value)
                result = f"{control.capitalize()} value set to {value}"
                action(value)

            else:
                result = self.__enable_binary_controls(control, action, mode)

            self.get_control_input_queue().send(self.ctrl)
            return result

        else:
            raise ValueError("Invalid control name value")

    def set_manual_control(self, manual_control: str, value: int) -> str:
        """
        Set manual control for OAK-D

        :param manual_control (str): The manual control name to set the value. ( exposure_time
         | sensitivity_iso | focus | white_balance)
        :param value (int): the integer value to set.

            Accepted range:

                exposure_time -> 1 .. 33000
                sensitivity_iso -> 100 .. 1600
                focus -> 0 .. 255
                white_balance -> 1000 .. 12000


        Return the result as a string
        """

        action = self.__manual_controls.get(manual_control, None)

        if action:
            if manual_control in ["exposure_time", "sensitivity_iso"]:

                if manual_control == "exposure_time":
                    self.__expTime = self.__put_in_range(manual_control, value)
                if manual_control == "sensitivity_iso":
                    self.__sensIso = self.__put_in_range(manual_control, value)

                action(self.__expTime, self.__sensIso)
                result = (
                    f"Exposure time: {self.__expTime} \nSensitivity: {self.__sensIso}"
                )

            else:
                value = self.__put_in_range(manual_control, value)
                action(value)
                result = f"{manual_control} set to {value}"

            self.get_control_input_queue().send(self.ctrl)
            return result

        else:
            raise ValueError("Invalid manual control name value")

    def create_yolo_detection_network(
        self,
        model_path: Path | str,
        json_path: Path | str,
        sync_nn: bool = True,
        confidence: float = 1.0,
    ) -> None:
        """
        Create a YOLO detection network. This function requires a blob model
        and a json file that you can get from a yolo model through the luxonis
        conversion tool available at https://tools.luxonis.com

        :param model_path (Path | str): The path for the blob model
        :param json_path (Path | str): The path for the json file
        :param sync_nn (bool): True for a synchronous neural network, which keeps
         frame capture synchronous with the inference process
        :param confidence (float): the confidence for valid detections. Default is
         the confindence from json file.

        """

        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model file not found, please check your path")
        if not Path(json_path).exists():
            raise FileNotFoundError(f"json file not found, please check your path")

        self.__get_model_settings(json_path)

        confidence = (
            confidence
            if confidence < 1.0 and confidence > 0.0
            else self.confidence_threshold
        )

        # Define sources and outputs
        camRgb = self.pipeline.create(dai.node.ColorCamera)
        detectionNetwork = self.pipeline.create(dai.node.YoloDetectionNetwork)
        xoutRgb = self.pipeline.create(dai.node.XLinkOut)
        nnOut = self.pipeline.create(dai.node.XLinkOut)

        xoutRgb.setStreamName("rgb")
        nnOut.setStreamName("nn")

        # Properties
        camRgb.setPreviewSize(self.width, self.height)
        camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        camRgb.setFps(35)

        # Network specific settings
        detectionNetwork.setConfidenceThreshold(confidence)
        detectionNetwork.setNumClasses(self.classes)
        detectionNetwork.setCoordinateSize(self.coordinates)
        detectionNetwork.setIouThreshold(self.iou_threshold)
        detectionNetwork.setBlobPath(model_path)
        detectionNetwork.setNumInferenceThreads(2)
        detectionNetwork.input.setBlocking(False)

        # Linking
        camRgb.preview.link(detectionNetwork.input)
        if sync_nn:
            detectionNetwork.passthrough.link(xoutRgb.input)
        else:
            camRgb.preview.link(xoutRgb.input)

        detectionNetwork.out.link(nnOut.input)

    def __get_model_settings(self, json_path: Path | str) -> None:
        """

        Function to get the model settings from json file (classes, confidence, labels,
        coordinates...)

        :param json_path (Path | str): The path for the json file

        """

        json_file: dict = OakdCam.__load_json(json_path)
        if not isinstance(json_file, dict):
            raise TypeError("JSON file is invalid")

        nn_config: Optional[dict] = json_file.get("nn_config", None)
        if nn_config is None:
            raise ValueError("Missing required key in JSON file: nn_config")

        metadata: Optional[dict] = nn_config.get("NN_specific_metadata", None)
        if metadata is None:
            raise ValueError(
                "Missing required key in JSON file: " "NN_specific_metadata"
            )

        mappings: Optional[dict] = json_file.get("mappings", None)
        if mappings is None:
            raise ValueError("Missing required key in JSON file: mappings")

        self.labels: Optional[list] = None
        self.classes: Optional[int] = None
        self.coordinates: Optional[int] = None
        self.anchors: Optional[list] = None
        self.anchor_masks: Optional[dict] = None
        self.iou_threshold: Optional[float] = None
        self.confidence_threshold: Optional[float] = None
        self.input_size: Optional[str] = None

        validation_dict = {
            "labels": mappings,
            "classes": metadata,
            "coordinates": metadata,
            "anchors": metadata,
            "anchor_masks": metadata,
            "iou_threshold": metadata,
            "confidence_threshold": metadata,
            "input_size": nn_config,
        }

        for name, prev_config in validation_dict.items():
            if (config := prev_config.get(name, None)) is None:
                raise ValueError(f"Missing required key in JSON file: {name}")
            else:
                self.__setattr__(f"{name}", config)

        if "x" not in self.input_size.lower():
            raise ValueError("Key 'input_size' must be 'WxH', e.g. '640x640'")

        self.width, self.height = [int(value) for value in self.input_size.split("x")]

    def depth_config(
        self,
        spatial_calculator: bool = False,
        calculation_algorithm: dai.SpatialLocationCalculatorAlgorithm = dai.SpatialLocationCalculatorAlgorithm.MEDIAN,
    ) -> None:
        """
        Configure depth settings for distance measurement applications. It defines the
        stereo, spatial location calculator (optional) and links the pipeline path.

        :param spatial_calculator (bool): set spatial location calculator as input to
         stereo depth link. SpatialLocationCalculator can calculate spatials coordinates
         within a defined Region of Interest (ROI), and forwards the depth map through the
         passthroughDepth output for visualization or processing.
        :param calculation_algorithm (dai.SpatialLocationCalculatorAlgorithm): the
         algorithm that will be used to calculate spatial coordinates. Default is MEDIAN

        """

        stereo = self.get_stereo_depth()
        xout_depth = self.pipeline.create(dai.node.XLinkOut)
        xout_depth.setStreamName("depth")

        # Overwrite properties:
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_ACCURACY)
        stereo.setSubpixel(True)

        if spatial_calculator:
            spatial_location_calculator, xoutSpatialData, xin_spatial_calc_config = (
                self.spatial_calculator_config(calculation_algorithm)
            )

            spatial_location_calculator.passthroughDepth.link(xout_depth.input)
            stereo.depth.link(spatial_location_calculator.inputDepth)

            spatial_location_calculator.out.link(xoutSpatialData.input)
            xin_spatial_calc_config.out.link(spatial_location_calculator.inputConfig)

        else:
            stereo.depth.link(xout_depth.input)

    def spatial_calculator_config(
        self,
        calc_algorithm: dai.SpatialLocationCalculatorAlgorithm = dai.SpatialLocationCalculatorAlgorithm.MEDIAN,
    ) -> Tuple[dai.node.SpatialLocationCalculator, dai.node.XLinkOut, dai.node.XLinkIn]:
        """
        Define settings for Spatial Location Calculator for applications that
        requires a ROI definition.

        :param calculation_algorithm (dai.SpatialLocationCalculatorAlgorithm): the
         algorithm that will be used to calculate spatial coordinates. Default is MEDIAN

        """

        xoutSpatialData = self.pipeline.create(dai.node.XLinkOut)
        xin_spatial_calc_config = self.pipeline.create(dai.node.XLinkIn)
        spatial_location_calculator = self.pipeline.create(
            dai.node.SpatialLocationCalculator
        )

        xoutSpatialData.setStreamName("spatialData")
        xin_spatial_calc_config.setStreamName("spatialCalcConfig")
        self.spatial_calc_config = dai.SpatialLocationCalculatorConfigData()
        self.spatial_calc_config.depthThresholds.lowerThreshold = 100
        self.spatial_calc_config.depthThresholds.upperThreshold = 10000
        self.spatial_calc_config.calculationAlgorithm = calc_algorithm
        spatial_location_calculator.inputConfig.setWaitForMessage(False)
        spatial_location_calculator.initialConfig.addROI(self.spatial_calc_config)

        return spatial_location_calculator, xoutSpatialData, xin_spatial_calc_config

    def update_spatial_calc_ROI(
        self, top_left: tuple[float, float], bottom_right: tuple[float, float]
    ) -> None:
        """
        Update the region of interest (ROI) in spatial calculator configs. It creates a
        dai.Rect to delimit the region using top left corner and bottom right corner
        past normalized.

        :param top_left (tuple[float, float]): a tuple with the normalized top left points.
         [0.0 ... 1.0].
        :param bottom_right (tuple[float, float]): a tuple with the normalized bottom right
         points. [0.0 ... 1.0].

        """

        if self.spatial_calc_config_inqueue is None and self.device is not None:
            self.spatial_calc_config_inqueue = self.device.getInputQueue(
                "spatialCalcConfig"
            )

        if self.spatial_calc_config is None:
            raise PipelineOrderingError(
                "Configure depth settings before call update ROI function"
            )

        top_left = dai.Point2f(top_left[0], top_left[1])
        bottom_right = dai.Point2f(bottom_right[0], bottom_right[1])

        self.spatial_calc_config.roi = dai.Rect(top_left, bottom_right)

        cfg = dai.SpatialLocationCalculatorConfig()
        cfg.addROI(self.spatial_calc_config)
        self.spatial_calc_config_inqueue.send(cfg)

    def create_spatial_detection_network(
        self,
        mn_model_path: Path | str,
        labels: list,
        confidence: float = 0.5,
        sync_nn: bool = True,
    ) -> None:
        """
        Function to create a Mobile Net Spatial Detection Network using stereo node
        aligned with color camera. It defines stereo, spatial detection network, rgb
        camera and configure its settings.

        :param mn_mnodel (Path | str): The path for the blob model
        :param labels (list): the list with the model labels
        :param confidence (float): the confidence for valid detections. Default is 0.5
        :param sync_nn (bool): True for a synchronous neural network, which keeps
         frame capture synchronous with the inference process

        """

        if not Path(mn_model_path).exists():
            raise FileNotFoundError(
                f"Mobile net model not found, please check your path"
            )
        if not isinstance(labels, list):
            raise TypeError("Passed labels parameter is not a list.")

        spatial_network = self.pipeline.create(
            dai.node.MobileNetSpatialDetectionNetwork
        )
        cam_rgb = self.pipeline.create(dai.node.ColorCamera)
        stereo = self.get_stereo_depth()

        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

        # Overwrite sub_pixel:
        stereo.setSubpixel(True)

        xout_rgb = self.pipeline.create(dai.node.XLinkOut)
        xout_nn = self.pipeline.create(dai.node.XLinkOut)
        xout_depth = self.pipeline.create(dai.node.XLinkOut)

        xout_rgb.setStreamName("rgb")
        xout_nn.setStreamName("detections")
        xout_depth.setStreamName("depth")

        cam_rgb.setPreviewSize(300, 300)
        cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam_rgb.setInterleaved(False)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)

        spatial_network.setBlobPath(mn_model_path)
        spatial_network.setConfidenceThreshold(confidence)
        spatial_network.input.setBlocking(False)
        spatial_network.setBoundingBoxScaleFactor(0.5)
        spatial_network.setDepthLowerThreshold(100)
        spatial_network.setDepthUpperThreshold(5000)

        cam_rgb.preview.link(spatial_network.input)

        if sync_nn:
            spatial_network.passthrough.link(xout_rgb.input)
        else:
            cam_rgb.preview.link(xout_rgb.input)

        spatial_network.out.link(xout_nn.input)

        stereo.depth.link(spatial_network.inputDepth)
        spatial_network.passthroughDepth.link(xout_depth.input)

    @staticmethod
    def __load_json(json_path: Path | str) -> dict:
        """
        Function to load json file from json_path and return it

        :param json_path (Path | str): The path for the json file

        """

        with open(json_path) as file:
            return json.load(file)
