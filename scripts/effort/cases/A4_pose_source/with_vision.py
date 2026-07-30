# @loc:boilerplate:begin
import nectar
from nectar.control import DroneFactory, MavrosConfig, PoseSource

nectar.init()
drone = DroneFactory.create(
    "mavros",
    MavrosConfig(pose_source=PoseSource.VISION, start_driver=False),
)
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=2.0)
drone.land()
# @loc:core:end
# @loc:boilerplate:begin
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
