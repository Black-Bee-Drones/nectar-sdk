import depthai as dai
import cv2

class OakdCam:

    """
    Class to initialize the pipeline and define the paramters for accessing OAKD images
    """
    
    def __init__(self)-> None:
        """
        OakdCam constructor: initializes the pipeline and configures cameras and their 
        board sockets
        """
        self.pipeline = dai.Pipeline()
        self.oak_dict = {1: ("rgb", dai.CameraBoardSocket.CAM_A),
                         2: ("left", dai.CameraBoardSocket.CAM_B),
                         3: ("right",  dai.CameraBoardSocket.CAM_C)}
        self.device = None
        

    def setup_camera(self, cam_num: int)-> None:
        """
        Function to set the camera type based on the camera number parameter

        :param cam_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam, 3 for
                              right monochrome cam 
        """
        
        self.cam_num = cam_num
        self.cam_type, self.boardSocket = self.oak_dict.get(self.cam_num, ("invalid", None))
        
        if self.cam_type != "invalid":

            if self.cam_type == "rgb":
                self.color_camera()

            else:
                self.mono_camera()


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
        cam.out.link(xout.input)

        return cam
    
    def getQueue_CamType(self) -> dai.DataOutputQueue:
        """
        Gets an output queue corresponding to cam_type. If it doesn't exist it throws.
            Use this function to get the output queue from cam_type defined in the "setup()" scope
        """
        
        return self.device.getOutputQueue(self.cam_type)
    
    def getQueue(self, stream_name: str) -> dai.DataOutputQueue:
        """
        Gets an output queue corresponding to stream name. If it doesn't exist it throws
        """

        return self.device.getOutputQueue(stream_name)
        

    def getFrame(self, queue: dai.DataOutputQueue) -> cv2.Mat:
        """
        Gets the cv frame from output queue wich is depthai.ImgFrame
        """

        return queue.get().getCvFrame()
    
    def clean(self):
        """
        Closes the connection to device
        """

        self.device.close()
    