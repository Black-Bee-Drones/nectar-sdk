import rclpy
from rclpy.node import Node

from std_msgs.msg import Int16

import numpy as np
from cvzone.HandTrackingModule import HandDetector

from mirela_sdk.image_processing.camera.image_handler import ImageHandler

import time
import math

class GestureRecognizer(Node):
    # Declare fingers gesture positions
    gestures: dict[tuple[int, ...], int] = {
        # List of fingers positions     #ID  # Action
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0): -1,  # NOTHING
        (1, 0, 0, 0, 0, 1, 0, 0, 0, 0): 1,  # LAND
        (0, 1, 0, 0, 0, 0, 1, 0, 0, 0): 2,  # UP
        (1, 1, 0, 0, 0, 1, 1, 0, 0, 0): 3,  # DOWN
        (0, 0, 0, 0, 0, 0, 1, 0, 0, 0): 4,  # LEFT
        (0, 1, 0, 0, 0, 0, 0, 0, 0, 0): 5,  # RIGHT
        (1, 0, 0, 0, 1, 0, 0, 0, 0, 0): 6,  # FLIP_RIGHT
        (0, 0, 0, 0, 0, 1, 0, 0, 0, 1): 7,  # FLIP_LEFT
        (0, 1, 0, 0, 1, 0, 0, 0, 0, 0): 8,  # FLIP_FRONT
        (0, 0, 0, 0, 0, 0, 1, 0, 0, 1): 9,  # FLIP_BACK
        (0, 1, 1, 0, 0, 0, 1, 1, 0, 0): 10,  # PHOTO
        (0, 1, 1, 1, 1, 0, 1, 1, 1, 1): 11,  # FRONT
        (0, 1, 1, 1, 0, 0, 1, 1, 1, 0): 12,  # BACK
        (0, 0, 0, 0, 1, 0, 0, 0, 0, 0): 13,  # YAW-CLOCKWISE
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 1): 14,  # YAW-COUNTERCLOCKWISE
        (1, 1, 1, 1, 1, 0, 0, 0, 0, 0): 15,  # Bye-Bye
    }

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
    ) -> None:
        """
        Initialize the GestureRecognizer class.

        :param min_detection_confidence: Minimum confidence value ([0.0, 1.0]) for hand detection.
        :param min_tracking_confidence: Minimum confidence value ([0.0, 1.0]) for hand tracking.
        """
        super().__init__("gesture_recognizer")

        self.detector = HandDetector(
            modelComplexity=model_complexity,
            detectionCon=min_detection_confidence,
            minTrackCon=min_tracking_confidence,
        )

        #tchauzingo_detect global variables
        self.turns = 0  #int variable --> saves the number of times the wrist-motion way changes
        self.old_ang = None #int variable --> saves the hand wrist-motion angle from the last loop
        self.motion = None #boolean variable --> 1 == increasing angle | 2 == decreasing angle
        self.old_motion = None #boolean variable --> saves the wrist-motion way from the last loop
        self.tchau_starttime = None
        self.left_indice = 0
        self.right_indice = 0

        self.msg = Int16()

        self.acao_pub = self.create_publisher(Int16, "/bebop/hands_action", 10)

        # "/bebop/image_raw"

        self.declare_parameter("image_source", "webcam")

        self.image_source = (
            self.get_parameter("image_source").get_parameter_value().string_value
        )

        self.image_handler = ImageHandler(
            self,
            image_source=self.image_source,
            image_processing_callback=self.process,
            show_result="Gesture Recognizer",
        )
        self.image_handler.run()

    def process(self, img: np.array) -> None:
        """
        Process the image to detect the hands and recognize the gestures.

        :param img: Image to be processed.
        :return: Processed image.
        """

        hands, img = self.detector.findHands(img)

        if hands and len(hands) == 2:
            self.get_logger().info(hands[0]["type"])
            if hands[0]["type"] == "Right": 
                self.right_indice = 0
                self.left_indice = 1
            else:
                self.right_indice = 1
                self.left_indice = 0
            
            fingers_right = self.detector.fingersUp(hands[self.right_indice])
            fingers_left = self.detector.fingersUp(hands[self.left_indice])

            self.msg.data = self.recognize_gesture(fingers_right, fingers_left)
            if self.msg.data == 15:
                self.tchauzinho_detect(hands[self.right_indice])

            else:    
                self.acao_pub.publish(self.msg)
            print(self.msg.data)

    def recognize_gesture(self, fingers_right: list, fingers_left: list) -> int:
        """
        Recognize the gesture based on the fingers positions.

        :param fingers_right: List of fingers positions for the right hand.
        :param fingers_left: List of fingers positions for the left hand.
        :return: Gesture ID.
        """
        return self.gestures.get(tuple(fingers_right + fingers_left), 0)

    def tchauzinho_detect(self, hand : dict):

        x0, y0, _ = hand['lmList'][0]  # Wrist coordinates
        x12, y12, _ = hand['lmList'][12]  # Tip of middle finger coordinates

        if self.tchau_starttime == None:
            self.tchau_starttime = time.time()

        if x12 == x0:
            hand_angulation = 90

        else:
            hand_angulation = int( math.degrees( math.atan( ( y12 - y0 ) / ( x12 - x0 ) ) ) / 25 )
        
        if self.old_ang != None:
            if hand_angulation > self.old_ang:
                self.motion = 1
            elif hand_angulation < self.old_ang:
                self.motion = 0

        if self.old_motion != None:
            if self.old_motion != self.motion:
                self.turns += 1
                self.tchau_starttime = time.time()

        self.old_motion = self.motion
        self.old_ang = hand_angulation

        if time.time() - self.tchau_starttime >= 10:
            self.old_motion = None
            self.old_ang = None
            self.turns = 0
            self.tchau_starttime = None


        if self.turns >= 4:
            self.old_motion = None
            self.old_ang = None
            self.turns = 0
            self.tchau_starttime = None
            self.get_logger().info("tchauzinho\n")


def main(args=None):
    rclpy.init(args=args)
    node = GestureRecognizer()
    rclpy.spin(node)


if __name__ == "__main__":
    main()
