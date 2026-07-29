# @loc:boilerplate:begin
from nectar.vision.camera import CameraFactory

cam = CameraFactory.from_source("webcam")
cam.start()
# @loc:boilerplate:end
# @loc:core:begin
frame = cam.get_frame()
if frame is None:
    raise RuntimeError("failed to read frame")
print(frame.shape)
# @loc:core:end
# @loc:boilerplate:begin
cam.close()
# @loc:boilerplate:end
