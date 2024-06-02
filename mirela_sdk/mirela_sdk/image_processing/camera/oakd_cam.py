import depthai as dai
import cv2

class OakdCam:

    def __init__(self)-> None:

        self.pipeline = dai.Pipeline()
        self.oak_dict = {1: ("rgb", dai.CameraBoardSocket.CAM_A),
                         2: ("left", dai.CameraBoardSocket.CAM_B),
                         3: ("right",  dai.CameraBoardSocket.CAM_C)}
        

    def setup_camera(self, cam_num: int)-> None:

        """
        :param cam_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam, 3 for
                              right monochromatic cam 
        """
        
        self.cam_num = cam_num
        self.cam_type, self.boardSocket = self.oak_dict.get(self.cam_num, ("invalid", None))
        
        if self.cam_type != "invalid":

            if self.cam_type == "rgb":
                self.color_camera()

            else:
                self.mono_camera()


    def color_camera(self) -> dai.node.ColorCamera:

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

        #coloca camera como entrada do link de comunição:
        cam.preview.link(xOut_rgb.input)

        return cam
    
    def mono_camera(self) -> dai.node.MonoCamera:

        cam = self.pipeline.createMonoCamera()
        cam.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)

        cam.setBoardSocket(self.boardSocket)
        xout = self.pipeline.createXLinkOut()
        xout.setStreamName(self.cam_type)
        cam.out.link(xout.input)

        return cam

    def getFrame(self, queue: dai.DataOutputQueue) -> cv2.Mat:

        return queue.get().getCvFrame()



        

        
