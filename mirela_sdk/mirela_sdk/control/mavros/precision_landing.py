#!/usr/bin/env python3

from rclpy.node import Node
from mirela_interfaces.msg._aruco_transforms import ArucoTransforms
from mirela_sdk.utils.process import ProcessUtils


class PrecisionLanding:
    
    """
    Class to initialize the precision landing process wich can be one package
    delivery as per application
    """

    def __init__(self, drone, node: Node, delivery: bool, aruco_target: int) -> None:

        """
        PrecisionLanding constructor
        ---------------------------
        :param drone (Drone): the mav being used in the application
        :param node (rclpy.node.Node): the ROS node to get the ArucoTransforms messages from topic
        :param delivery (bool): True to execute the package delivery, False to execute the landing. 
        :param aruco_target(int): the aruco id target to execute the process. 
        """

        self.state = 0
        self.node = node
        self.delivery = delivery
        self.aruco_target = aruco_target
        self.kp_linear = 0.2
        self.kl = 0.05
        self.drone = drone
        self.flag = False

        self._aruco_sub = self.node.create_subscription(ArucoTransforms, "/aruco/pose_estimate", 
                                                   self.__sub_aruco_callback, 10)
        
        ProcessUtils.start_process("ros2 run mirela_sdk aruco_node --ros-args -p image_source:='webcam'", 
                                   "precision_landing")



    def __sub_aruco_callback(self, aruco: ArucoTransforms) -> None:
        """
        Callback to receive the aruco messages and process the infos
        """

        self.aruco_id = aruco.id
        self.translation_x = aruco.translation.x
        self.translation_y = aruco.translation.y
        self.translation_z = aruco.translation.z

        altitude = self.drone.get_rng_alt.range
        landing_area = self.kl*altitude

        if altitude < 8  and not self.flag:
            self.flag = True
            self.drone.set_mode('GUIDED')

        if(self.aruco_id == self.aruco_target):
            if altitude > 1.2 and self.flag:
        
                if (self.state == 0):
                    if (abs(self.translation_x) > landing_area) or (abs(self.translation_y) > 
                                                                        landing_area):
                        
                        print("\033[1;34m-- Move to aruco\033[m")
                        self.__move_to_aruco()

                    elif(abs(self.translation_x) < landing_area) and (abs(self.translation_y) < 
                                                                          landing_area):
                        
                        self.node.get_logger().info("\033[32mDrone no centro da Aruco\033[m")
                        self.state = 1
                    
                if (self.state == 1):
                    self.node.get_logger().info("\033[32mDescendo o drone\033[m")
                    self.drone.offboard_velocity(0, 0, -0.4, 0, False)  
                    self.state = 0
                    
        
            elif altitude <= 1.2 and not self.delivery:
                self.drone.land()

            elif altitude <= 1.2 and self.delivery:
                self.drone.do_servo(1, 1500)
                self.drone.rtl(10, False)

        else:
            self.node.get_logger().info(f"\033[31mAruco id {self.aruco_target} not detected\033[m")   
        

    def __move_to_aruco(self):
        """
        Function to calculate and move the mav to ArUco Marker center
        """
        linear_vel_x = self.kp_linear*self.translation_x
        linear_vel_y = self.kp_linear*self.translation_y

        self.drone.offboard_velocity(linear_vel_x, linear_vel_y, 0, 0, False)
