import depthai as dai
import cv2

class OakdCam:

    """
    Class to initialize the pipeline and define the parameters for accessing OAKD images

    Note: all pipeline links must be configured before starting it. Some ready settings in this
    class prevent it, but for standalone applications you must pay attention to this.

    """
    
    AUTOEXPOSURE =           "autoexposure"
    ANTI_BANDING_MODE = "anti_banding_mode"
    AWB_MODE =                   "awb_mode"
    EFFECT_MODE =             "effect_mode"
    AUTOFOCUS =                 "autofocus"
    AE_COMP =                     "ae_comp"
    BRIGHTNESS =               "brightness"
    CONTRAST =                   "contrast"
    SATURATION =               "saturation"
    SHARPNESS =                 "sharpness"
    LUMA_DENOISE =           "luma_denoise"
    CHROMA_DENOISE =       "chroma_denoise"
    EXPOSURE_TIME =         "exposure_time"
    SENSITIVITY_ISO =     "sensitivity_iso"
    FOCUS =                         "focus"
    WHITE_BALANCE =         "white_balance"

    
    def __init__(self)-> None:
        """
        OakdCam constructor: initializes the pipeline and configures cameras with their 
        board sockets
        """
        self.pipeline = dai.Pipeline()
        self.oak_dict = {1: ("rgb",   dai.CameraBoardSocket.CAM_A),
                         2: ("left",  dai.CameraBoardSocket.CAM_B),
                         3: ("right", dai.CameraBoardSocket.CAM_C)}
        self.device = None
        

    def setup_camera(self, 
                     cam_num: int, 
                     link_out: bool = True, 
                     set_control: bool = True) -> dai.node.ColorCamera | dai.node.MonoCamera | None:
        """
        Function to set the camera type based on the camera number parameter

        :param cam_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam, 
         3 for right monochrome cam 
        :param link_out (bool): link the camera output with xout input, 
         False to wait for another application
        :param set_control (bool): True for set initial control settings. False for otherwise
        """
        
        self.link_out = link_out
        self.cam_num = cam_num
        self.cam_type, self.boardSocket = self.oak_dict.get(self.cam_num, ("invalid", None))

        camera = None
        
        if self.cam_type != "invalid":

            if self.cam_type == "rgb":
                camera = self.color_camera()
                if set_control:
                    self.__set_control_input(camera)
                    self.__oakd_controls()

            else:
                camera = self.mono_camera()

        else: raise ValueError("Invalid value for cam_num")

        return camera


    def init_cam(self, full_speed: bool = False) -> dai.Device:
        """
        Initialize the device and return it
        """

        usb_speed = dai.UsbSpeed.FULL if full_speed else dai.UsbSpeed.HIGH

        self.device = dai.Device(self.pipeline, maxUsbSpeed=usb_speed)

        return self.device
    
    
    def color_camera(self) -> dai.node.ColorCamera:
        """
        Link device to host, set resolution, Isp scale and fps to get the color camera
        """

        #ativo a camera rgb
        cam = self.pipeline.createColorCamera()
        #seleciono a câmera rgb:
        cam.setBoardSocket(self.boardSocket)
        #setar resolução:
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        #setar tamanho
        cam.setIspScale(1,2) # 540P
        #setar fps
        cam.setFps(35)
        
        #criar link de comunicação da camera com o host(pc)
        xOut_rgb = self.pipeline.createXLinkOut()
        xOut_rgb.setStreamName("rgb")

        #coloca camera como entrada do link de comunicação:
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

        if self.link_out: cam.out.link(xout.input)

        return cam
    
    def getQueue_CamType(self) -> dai.DataOutputQueue:
        """
        Gets an output queue corresponding to cam_type. If it doesn't exist it throws.
            Use this function to get the output queue from cam_type defined in the "setup()" scope
        """
        
        return self.device.getOutputQueue(self.cam_type)
    
    
    def getQueue(self, 
                 stream_name: str, 
                 maxSize: int, 
                 blocking: bool = True) -> dai.DataOutputQueue:
        """
        Gets an output queue corresponding to stream name. If it doesn't exist it throws

        :param stream_name (str): the stream name for output queue
        :param maxSize (int): max size of the queue
        :param blocking (bool): True for block the return of the function until 
         arrive new msgs in the queue. False for otherwise
        """

        return self.device.getOutputQueue(stream_name, maxSize, blocking = blocking)
        

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

        self.stereo_links = {"disparity":      stereo.disparity.link, 
                             "depth":          stereo.depth.link, 
                             "rectifiedLeft":  stereo.rectifiedLeft.link, 
                             "rectifiedRight": stereo.rectifiedRight.link, 
                             "syncedLeft":     stereo.syncedLeft.link, 
                             "syncedRight":    stereo.syncedRight.link}

        mono_left = self.setup_camera(2, False)
        mono_right = self.setup_camera(3, False)

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
        
        for stream_name in stream_names:
        
            link = self.stereo_links.get(stream_name, None)

            if link:

                xout = self.pipeline.createXLinkOut()
                xout.setStreamName(stream_name)
                link(xout.input)

            else: raise ValueError("Invalid stream name value")

      
    def create_imu(self) -> dai.node.IMU:

        """
        Create an IMU sensor and return it.

        Note: OAK-D-LITE doesn't have IMU
        """

        self.imu = self.pipeline.createIMU()
        xout = self.pipeline.createXLinkOut()
        xout.setStreamName("imu")

        self.imu_sensors = {"accelerometer": dai.IMUSensor.ACCELEROMETER, 
                            "gyroscope": dai.IMUSensor.GYROSCOPE_RAW}
        
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

        else: raise ValueError("Invalid sensor name value")


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
        self.__controls = {OakdCam.AUTOEXPOSURE:      self.ctrl.setAutoExposureEnable,
                           OakdCam.ANTI_BANDING_MODE: self.ctrl.setAntiBandingMode,
                           OakdCam.AWB_MODE:          self.ctrl.setAutoWhiteBalanceMode,
                           OakdCam.EFFECT_MODE:       self.ctrl.setEffectMode,
                           OakdCam.AUTOFOCUS:         self.ctrl.setAutoFocusMode, 
                           OakdCam.AE_COMP:           self.ctrl.setAutoExposureCompensation,
                           OakdCam.BRIGHTNESS:        self.ctrl.setBrightness, 
                           OakdCam.CONTRAST:          self.ctrl.setContrast, 
                           OakdCam.SATURATION:        self.ctrl.setSaturation, 
                           OakdCam.SHARPNESS:         self.ctrl.setSharpness, 
                           OakdCam.LUMA_DENOISE:      self.ctrl.setLumaDenoise, 
                           OakdCam.CHROMA_DENOISE:    self.ctrl.setChromaDenoise}
        
        self.__manual_controls = {OakdCam.EXPOSURE_TIME:   self.ctrl.setManualExposure,
                                  OakdCam.SENSITIVITY_ISO: self.ctrl.setManualExposure, 
                                  OakdCam.FOCUS:           self.ctrl.setManualFocus, 
                                  OakdCam.WHITE_BALANCE:   self.ctrl.setManualWhiteBalance}
        
        self.__range_control = ["brightness", "contrast", "saturation", "ae_comp", 
                                "sharpness", "luma_denoise", "chroma_denoise"]
        
        self.__expTime = 20000
        self.__sensIso = 800
        
        self.awb_modes =     {name: mode for name, mode in vars(self.ctrl.AutoWhiteBalanceMode).items() 
                              if name.isupper()}
        self.antband_modes = {name: mode for name, mode in vars(self.ctrl.AntiBandingMode).items() 
                              if name.isupper()}
        self.effect_modes =  {name: mode for name, mode in vars(self.ctrl.EffectMode).items() 
                              if name.isupper()}
        self.aut_foc_modes = {name: mode for name, mode in vars(self.ctrl.AutoFocusMode).items() 
                              if name.isupper()}
        
        self.__control_modes = [OakdCam.AWB_MODE, 
                                OakdCam.ANTI_BANDING_MODE, 
                                OakdCam.EFFECT_MODE,       
                                OakdCam.AUTOFOCUS]


    def __enable_binary_controls(self, 
                                 control: str, 
                                 action: callable, 
                                 mode = None) -> str:

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

        match(control):
            case "ae_comp":return max(-9, min(9, value))
            case "brightness" | "contrast" | "saturation": return max(-10, min(10, value))
            case "sensitivity_iso": return max(100, min(1600, value))
            case "exposure_time": return max(1, min(33000, value))
            case "focus": return max(0, min(255, value))
            case "white_balance": return max(1000, min(12000, value))
            case _: return max(0, min(4, value))


    def get_control_input_queue(self) -> dai.DataInputQueue:

        """
        Get the input control queue
        """

        return self.device.getInputQueue("control")
    

    def set_control(self, 
                     control: str, 
                     value: int = 0, 
                     mode = None) -> str:

        """
        Set the variable control for OAK-D

        :param control (str): the control to change the value ( brightness | contrast | saturation
         | sharpness | luma_denoise | chroma_denoise | ae_comp | autoexposure | anti_banding_mode | awb_mode
         | effect_mode | autofocus )
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
        
        else: raise ValueError("Invalid control name value")


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

                if manual_control == "exposure_time": self.__expTime = self.__put_in_range(manual_control, 
                                                                                           value)
                if manual_control == "sensitivity_iso": self.__sensIso = self.__put_in_range(manual_control,
                                                                                             value)
                
                action(self.__expTime, self.__sensIso)
                result = f"Exposure time: {self.__expTime} \nSensitivity: {self.__sensIso}"

            else:
                value = self.__put_in_range(manual_control, value)
                action(value)
                result = f"{manual_control} set to {value}"
            
            self.get_control_input_queue().send(self.ctrl)
            return result

        else: raise ValueError("Invalid manual control name value")

        
    def clean(self):
        """
        Closes the connection to device
        """

        self.device.close()
    