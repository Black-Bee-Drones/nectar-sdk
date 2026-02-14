cmake_minimum_required(VERSION 3.8)
project(mirela_sdk)

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

# =============================================================================
# C++ Include directories (for future C++ nodes)
# =============================================================================
# include_directories(include)

# =============================================================================
# C++ Executables (add C++ nodes here when ready)
# =============================================================================
# Example:
# add_executable(cpp_node src/cpp_node.cpp)
# ament_target_dependencies(cpp_node rclcpp std_msgs)
# install(TARGETS cpp_node DESTINATION lib/${PROJECT_NAME})


ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  mirela_sdk/interface/app.py
  mirela_sdk/vision/nodes/aruco_node.py
  mirela_sdk/vision/nodes/color_calibration_node.py
  mirela_sdk/vision/nodes/click_color_calibration_node.py
  mirela_sdk/vision/camera/calibration/calibration.py
  mirela_sdk/vision/nodes/line_detection_node.py
  mirela_sdk/vision/nodes/webcam_publisher_node.py
  mirela_sdk/examples/vision/camera_example.py
  mirela_sdk/examples/vision/depth_example.py
  mirela_sdk/examples/ai/detector_example.py
  mirela_sdk/control/pid/pid_node.py
  DESTINATION lib/${PROJECT_NAME}
)


install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY mirela_sdk/control/config/
  DESTINATION share/${PROJECT_NAME}/control/config
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY mirela_sdk/interface/images/
  DESTINATION share/${PROJECT_NAME}/interface/images
  FILES_MATCHING PATTERN "*.png"
)

install(DIRECTORY mirela_sdk/ai/detection/configs/
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
