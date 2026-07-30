# @loc:boilerplate:begin
import nectar
from nectar.control import DroneFactory, MavrosConfig, NavigationMethod, PoseSource

nectar.init()
drone = DroneFactory.create(
    "mavros", MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
)
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3, method=NavigationMethod.POSITION)
drone.land()
# @loc:core:end
# @loc:boilerplate:begin
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
