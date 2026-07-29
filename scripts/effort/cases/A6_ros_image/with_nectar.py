# @loc:boilerplate:begin
import nectar
from nectar.vision.camera import CameraFactory

nectar.init()
cam = CameraFactory.from_source("/camera/color/image_raw")
cam.start()
# @loc:boilerplate:end
# @loc:core:begin
frame = cam.get_frame(wait_for_new=True, timeout=2.0)
if frame is None:
    raise RuntimeError("failed to read frame")
print(frame.shape)
# @loc:core:end
# @loc:boilerplate:begin
cam.close()
nectar.shutdown()
# @loc:boilerplate:end
