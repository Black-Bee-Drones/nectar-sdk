#!/usr/bin/env python3

import subprocess
import shlex
from rclpy.node import Node
from mirela_interfaces.msg._aruco_transforms import ArucoTransforms


class PrecisionLanding:

    def __init__(self, drone, node: Node) -> None:
        self.state = 0
        self.node = node
        self.aruco_target = 800
        self.kp_linear = 0.2
        self.kl = 0.05
        self.drone = drone
        self.flag = False

        self._aruco_sub = node.create_subscription(ArucoTransforms, "aruco/pose_estimate", 
                                                   self.sub_aruco_callback, 10)
        
        
    def init_aruco_node():

        command = [
            "ros2",
            "run",
            "mirela_sdk",
            "aruco_node",
        ]

        command_str = " ".join(command)

        process = subprocess.Popen(shlex.split(f'gnome-terminal -- bash -c "{command_str}"'))

        process.communicate()

        if process.returncode != 0:
            print(f"\033[91mErro ao iniciar aruco_node: {process.returncode}\033[0m")
        else:
            print(f"\033[92maruco_node iniciado com sucesso\033[0m")



    def sub_aruco_callback(self, aruco: ArucoTransforms):
        self.aruco_id = aruco.id
        self.translation_x = aruco.translation.x
        self.translation_y = aruco.translation.y
        self.translation_z = aruco.translation.z

        altitude = self.drone.get_rng_alt.range
        landing_area = self.kl*altitude

        if altitude < 8  and not self.flag:
            self.flag = True
            self.drone.set_mode('GUIDED')

        if(self.aruco_id == self.aruco_target) and (self.aruco_id is not None):
            if altitude > 2 and self.flag:
        
                if (self.state == 0):
                    if (abs(self.translation_x) > landing_area) or (abs(self.translation_y) > 
                                                                        landing_area):
                        
                        print("\033[1;34m-- Move to aruco\033[m")
                        self.move_to_aruco()

                    elif(abs(self.translation_x) < landing_area) and (abs(self.translation_y) < 
                                                                          landing_area):
                        
                        self.node.get_logger().info("\033[32mDrone no centro da Aruco\033[m")
                        self.state = 1
                    
                if (self.state == 1):
                    self.node.get_logger().info("\033[32mDescendo o drone\033[m")
                    self.drone.offboard_velocity(0, 0, -0.4, 0, False)  
                    self.state = 0
                    
        
            elif altitude <= 2:
                self.drone.land()

        else:
            self.node.get_logger().info("\033[31mNo aruco detected\033[m")   
        

    def move_to_aruco(self):
        
        linear_vel_x = self.kp_linear*self.translation_x
        linear_vel_y = self.kp_linear*self.translation_y

        self.drone.offboard_velocity(linear_vel_x, linear_vel_y, 0, 0, False)
