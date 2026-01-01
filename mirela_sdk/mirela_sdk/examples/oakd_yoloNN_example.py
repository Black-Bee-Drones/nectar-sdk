from pathlib import Path
import time
import cv2
import numpy as np
from mirela_sdk.image_processing.camera.oakd_cam import OakdCam

# Paths (set your path for test): 
path = Path(__file__).parent.resolve().absolute()
nnPath = str(path / 'blob/yolo11n.blob')
json_path = str(path / 'blob/yolo11n.json')

# OAK-D settings: 
sync_nn = True
oakd = OakdCam()
oakd.create_yolo_detection_network(model_path=nnPath, 
                                   json_path=json_path, 
                                   sync_nn=sync_nn, 
                                   confidence = 0.4)
oakd.init_cam()

qRgb = oakd.getQueue("rgb", maxSize=4, blocking=False)
qDet = oakd.getQueue("nn", maxSize=4, blocking=False)

# Stream settings:
frame = None
detections = []
startTime = time.monotonic()
counter = 0


while True:
    if sync_nn:
        inRgb = qRgb.get()
        inDet = qDet.get()
    else:
        inRgb = qRgb.tryGet()
        inDet = qDet.tryGet()

    if inRgb is not None:
        frame = inRgb.getCvFrame()
        cv2.putText(frame, "NN fps: {:.2f}".format(counter / (time.monotonic() - startTime)),
                    (2, frame.shape[0] - 4), cv2.FONT_HERSHEY_TRIPLEX, 0.4, (255, 255, 255))

    if inDet is not None:
        detections = inDet.detections
        counter += 1

    if frame is not None:

        for detection in detections:

            # Normalize the coordinates that are (0,..., 1) according to frame shape
            bbox = (detection.xmin, detection.ymin, detection.xmax, detection.ymax)
            normVals = np.full(len(bbox), frame.shape[0])
            normVals[::2] = frame.shape[1]
            bbox = (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

            # Put labels, confidence and coordinates rectangle on the frame
            cv2.putText(frame, oakd.labels[detection.label], (bbox[0] + 10, bbox[1] + 20), 
                                                        cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
            cv2.putText(frame, f"{int(detection.confidence * 100)}%", (bbox[0] + 10, bbox[1] + 40), 
                                                        cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)

        cv2.imshow("Detections", frame)

    if cv2.waitKey(1) == ord('q'):
        cv2.destroyAllWindows()
        oakd.clean()
        break