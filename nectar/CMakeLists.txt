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
  nectar/interface/app.py
  nectar/vision/nodes/aruco_node.py
  nectar/vision/nodes/color_calibration_node.py
  nectar/vision/camera/calibration/calibration.py
  nectar/vision/nodes/line_detection_node.py
  nectar/vision/nodes/camera_publisher_node.py
  nectar/examples/vision/camera_example.py
  nectar/examples/vision/depth_example.py
  nectar/examples/vision/t265_example.py
  nectar/examples/vision/collect_photos.py
  nectar/examples/ai/detector_example.py
  nectar/examples/ai/classifier_example.py
  nectar/examples/sensors/rangefinder_example.py
  nectar/control/pid/pid_node.py
  nectar/sensors/nodes/rangefinder_node.py
  nectar/control/localization/nodes/vision_pose_node.py
  nectar/control/localization/nodes/path_window_node.py
  ../scripts/simulation/gz_vision_source.py
  DESTINATION lib/${PROJECT_NAME}
)


install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}
)

install(DIRECTORY nectar/control/ardupilot/config/
  DESTINATION share/${PROJECT_NAME}/control/ardupilot/config
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY nectar/control/px4/config/
  DESTINATION share/${PROJECT_NAME}/control/px4/config
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

install(DIRECTORY nectar/ai/segmentation/configs/
  DESTINATION share/${PROJECT_NAME}/ai/segmentation/configs
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY nectar/ai/classification/configs/
  DESTINATION share/${PROJECT_NAME}/ai/classification/configs
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY nectar/control/localization/config/
  DESTINATION share/${PROJECT_NAME}/control/localization/config
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY nectar/control/localization/rviz/
  DESTINATION share/${PROJECT_NAME}/control/localization/rviz
  FILES_MATCHING PATTERN "*.rviz"
)

install(DIRECTORY nectar/control/mavros/config/
  DESTINATION share/${PROJECT_NAME}/control/mavros/config
  FILES_MATCHING PATTERN "*.yaml"
)

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
  FILES_MATCHING PATTERN "*.launch.py"
)

install(DIRECTORY simulation/
  DESTINATION share/${PROJECT_NAME}/simulation
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # Style/format linting is owned by ruff (pyproject.toml + pre-commit + the
  # code-quality CI workflow). Disable the overlapping ament linters so they do
  # not enforce a conflicting convention; ruff is the single source of truth.
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  set(ament_cmake_flake8_FOUND TRUE)
  set(ament_cmake_pep257_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  # Tier-2 functional suite. Each module is its own pytest target so colcon runs
  # it in a separate process -- rclpy contexts, Qt and torch do not compose
  # cleanly in one. Hardware-/GPU-gated tests are deselected by default
  # (addopts in pyproject.toml); checks self-skip when a dep/device/sim is absent.
  find_package(ament_cmake_pytest REQUIRED)
  set(_nectar_functional_dir "${CMAKE_CURRENT_SOURCE_DIR}/test/functional")
  ament_add_pytest_test(functional_core        "${_nectar_functional_dir}/test_core.py"        TIMEOUT 120)
  ament_add_pytest_test(functional_control     "${_nectar_functional_dir}/test_control.py"     TIMEOUT 120)
  ament_add_pytest_test(functional_vision      "${_nectar_functional_dir}/test_vision.py"      TIMEOUT 120)
  ament_add_pytest_test(functional_sensors     "${_nectar_functional_dir}/test_sensors.py"     TIMEOUT 120)
  ament_add_pytest_test(functional_localization "${_nectar_functional_dir}/test_localization.py" TIMEOUT 120)
  ament_add_pytest_test(functional_interface   "${_nectar_functional_dir}/test_interface.py"   TIMEOUT 120)
  ament_add_pytest_test(functional_simulation  "${_nectar_functional_dir}/test_simulation.py"  TIMEOUT 180)
  ament_add_pytest_test(functional_ai          "${_nectar_functional_dir}/test_ai.py"          TIMEOUT 600)
endif()

ament_package()
