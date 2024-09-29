import cv2
import numpy as np
from mirela_sdk.image_processing.camera.oakd_cam import OakdCam

oakd = OakdCam()
stereo = oakd.get_stereo_depth()

oakd.configure_stereo_node_output(["disparity", "rectifiedLeft", "rectifiedRight"])
oakd.init_cam()

disp_queue = oakd.getQueue("disparity", maxSize = 1, blocking = False)
rectifiedLeftQueue = oakd.getQueue("rectifiedLeft", 
                                           maxSize=1, blocking=False)
rectifiedRightQueue=oakd.getQueue("rectifiedRight", 
                                           maxSize=1, blocking=False)

#Valor para multiplicar a matriz de disparidade para que os valores fiquem entre 0 e 255
disparityMultiplier = 255 / stereo.initialConfig.getMaxDisparity()

while cv2.waitKey(1) & 0xFF != ord("q"):

    disp = oakd.getFrame(disp_queue)
    left = oakd.getFrame(rectifiedLeftQueue)
    right = oakd.getFrame(rectifiedRightQueue)

    disp = (disp * disparityMultiplier).astype(np.uint8)

    #Aplica um mapeamento dos valores de disparidade em diferentes cores para a visualização
    #Vai de azul (distante) a vermelho (perto)
    disp = cv2.applyColorMap(disp, cv2.COLORMAP_JET)

    cv2.imshow("Left camera", left)
    cv2.imshow("Right camera", right)
    cv2.imshow("Disparity", disp)

cv2.destroyAllWindows()
oakd.clean()
