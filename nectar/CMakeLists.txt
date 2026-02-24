cmake_minimum_required(VERSION 3.8)
project(nectar)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(OpenCV REQUIRED)
find_package(realsense2 REQUIRED)

# =============================================================================
# C++ Include directories
# =============================================================================
include_directories(
  ${OpenCV_INCLUDE_DIRS}
  ${realsense2_INCLUDE_DIRS}
)

# =============================================================================
# C++ Executables
# =============================================================================

# depth_cluster_node — BFS depth clustering obstacle detector for RealSense.
# Publishes on /<namespace>/obstacle_detected|distance|direction topics
# consumed by ROSObstacleDetector.
add_executable(depth_cluster_node
  nectar/control/obstacles/depth_cluster.cpp
)
ament_target_dependencies(depth_cluster_node
  rclcpp
  std_msgs
)
target_link_libraries(depth_cluster_node
  ${OpenCV_LIBS}
  ${realsense2_LIBRARY}
)
install(TARGETS depth_cluster_node
  DESTINATION lib/${PROJECT_NAME}
)


ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  nectar/interface/app.py
  nectar/vision/nodes/aruco_node.py
  nectar/vision/nodes/color_calibration_node.py
  nectar/vision/nodes/click_color_calibration_node.py
  nectar/vision/camera/calibration/calibration.py
  nectar/vision/nodes/line_detection_node.py
  nectar/vision/nodes/webcam_publisher_node.py
  nectar/examples/vision/camera_example.py
  nectar/examples/vision/depth_example.py
  nectar/examples/ai/detector_example.py
  nectar/control/pid/pid_node.py
  DESTINATION lib/${PROJECT_NAME}
)


install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY nectar/control/config/
  DESTINATION share/${PROJECT_NAME}/control/config
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY nectar/interface/images/
  DESTINATION share/${PROJECT_NAME}/interface/images
  FILES_MATCHING PATTERN "*.png"
)

install(DIRECTORY nectar/ai/detection/configs/
  DESTINATION share/${PROJECT_NAME}/ai/detection/configs
  FILES_MATCHING PATTERN "*.yaml"
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_pytest REQUIRED)
endif()

ament_package()
