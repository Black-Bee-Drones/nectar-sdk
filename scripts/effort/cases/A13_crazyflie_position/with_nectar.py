# @loc:boilerplate:begin
import nectar
from nectar.control import CrazyflieConfig, DroneFactory

nectar.init()
drone = DroneFactory.create(
    "crazyflie", CrazyflieConfig(cf_name="cf231", start_driver=False)
)
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=0.5)
drone.move_to(x=0.3, y=0.0, z=None, precision=0.1)
drone.land()
# @loc:core:end
# @loc:boilerplate:begin
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
