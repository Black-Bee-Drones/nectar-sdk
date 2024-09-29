import depthai as dai
import cv2

class OakdCam:

    """
    Class to initialize the pipeline and define the parameters for accessing OAKD images
    """
    
    def __init__(self)-> None:
        """
        OakdCam constructor: initializes the pipeline and configures cameras with their 
        board sockets
        """
        self.pipeline = dai.Pipeline()
        self.oak_dict = {1: ("rgb", dai.CameraBoardSocket.CAM_A),
                         2: ("left", dai.CameraBoardSocket.CAM_B),
                         3: ("right",  dai.CameraBoardSocket.CAM_C)}
        self.device = None
        

    def setup_camera(self, 
                     cam_num: int, 
                     link_out: bool = True) -> dai.node.ColorCamera | dai.node.MonoCamera | None:
        """
        Function to set the camera type based on the camera number parameter

        :param cam_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam, 
         3 for right monochrome cam 
        :param link_out (bool): link the camera output with xout input, 
         False to wait for another application
        """
        
        self.link_out = link_out
        self.cam_num = cam_num
        self.cam_type, self.boardSocket = self.oak_dict.get(self.cam_num, ("invalid", None))

        camera = None
        
        if self.cam_type != "invalid":

            if self.cam_type == "rgb":
                camera = self.color_camera()

            else:
                camera = self.mono_camera()

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
        Link device to host, set resolution and preview size to get the color camera
        """

        #ativo a camera rgb
        cam = self.pipeline.createColorCamera()
        #seleciono a câmera rgb:
        cam.setBoardSocket(self.boardSocket)
        #setar resolução:
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        #setar tamanho
        cam.setPreviewSize(960, 540)
        #setar fps
        cam.setFps(30)
        
        #criar link de comunicação da camera com o host(pc)
        xOut_rgb = self.pipeline.createXLinkOut()
        xOut_rgb.setStreamName("rgb")

        #coloca camera como entrada do link de comunicação:
        cam.preview.link(xOut_rgb.input)

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
        param stream_name (str): the stream name for output queue
        param maxSize (int): max size of the queue
        param blocking (bool): True for block the return of the function until 
        arrive new msgs in the queue. False for otherwise
        """

        return self.device.getOutputQueue(stream_name, maxSize, blocking = blocking)
        

    def getFrame(self, queue: dai.DataOutputQueue) -> cv2.Mat:
        """
        Gets the cv frame from output queue wich is depthai.ImgFrame
        param queue (dai.DataOutputQueue): the output queue from getQueue function
        """

        return queue.get().getCvFrame()
    
    
    def get_stereo_depth(self) -> dai.node.StereoDepth:

        """
        Set stereo settings and get it to use. 
        """

        stereo = self.pipeline.createStereoDepth()
        stereo.setLeftRightCheck(True)

        self.stereo_links = {"disparity": stereo.disparity.link, 
                             "depth": stereo.depth.link, 
                             "rectifiedLeft": stereo.rectifiedLeft.link, 
                             "rectifiedRight": stereo.rectifiedRight.link, 
                             "syncedLeft": stereo.syncedLeft.link, 
                             "syncedRight": stereo.syncedRight.link}

        mono_left = self.setup_camera(2, False)
        mono_right = self.setup_camera(3, False)

        mono_left.out.link(stereo.left)
        mono_right.out.link(stereo.right)

        return stereo
        

    def configure_stereo_node_output(self, stream_names: list[str]) -> None:

        """
        Set the stereo output requested

        param stream_names list[str]: stream names to configure
        ("disparity", "depth", "rectifiedLeft", "rectifiedRight", "syncedLeft", "syncedRight")
        """
        
        for stream_name in stream_names:
        
            link = self.stereo_links.get(stream_name, None)

            if link:

                xout = self.pipeline.createXLinkOut()
                xout.setStreamName(stream_name)
                link(xout.input)

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
        
        param sensor_name (str): the sensor name to enable ("accelerometer", "gyroscope")
        param rate (int): the measurement frequency, in Hz, of the sensor. Max frequencies: 
        accelerometer -> 512 Hz, gyroscope -> 1000 Hz
        """

        sensor = self.imu_sensors.get(sensor_name, (None, None))
        
        if sensor:

            self.imu.enableIMUSensor(sensor, rate)


    def clean(self):
        """
        Closes the connection to device
        """

        self.device.close()
    