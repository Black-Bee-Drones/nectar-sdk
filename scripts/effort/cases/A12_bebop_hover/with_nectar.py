# @loc:boilerplate:begin
import nectar
from nectar.control import BebopConfig, DroneFactory

nectar.init()
drone = DroneFactory.create("bebop", BebopConfig(start_driver=False))
# @loc:boilerplate:end
# @loc:core:begin
drone.takeoff(altitude=1.5)
drone.move_velocity(vx=0.3, duration=2.0)
drone.land()
# @loc:core:end
# @loc:boilerplate:begin
drone.cleanup()
nectar.shutdown()
# @loc:boilerplate:end
