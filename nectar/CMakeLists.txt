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


# =============================================================================
# Python package install
# -----------------------------------------------------------------------------
# ament_python_install_package() has no exclude API: it installs the whole
# PACKAGE_DIR and only skips *.pyc / __pycache__ (ament_cmake_python). Local
# AI datasets, training outputs, and tool caches under nectar/ must not enter
# install/ . Workaround: rsync a trimmed tree into the
# build dir and pass that as PACKAGE_DIR. Training still uses the source tree
# via nectar.ai.paths (DEFAULT_DATA_DIR / DEFAULT_OUTPUT_DIR).
# Do not exclude ai/*/datasets/ — those are Python source modules.
# =============================================================================
find_program(RSYNC_EXECUTABLE rsync)
if(NOT RSYNC_EXECUTABLE)
  message(FATAL_ERROR
    "rsync is required to stage the nectar Python package without datasets/caches. "
    "Install it (e.g. apt install rsync) and re-run cmake.")
endif()

set(_NECTAR_PY_STAGE "${CMAKE_CURRENT_BINARY_DIR}/python_stage/nectar")
set(_NECTAR_PY_RSYNC_EXCLUDES
  # AI bulk data (gitignored; paths.py resolves source tree)
  --exclude ai/data/
  --exclude ai/outputs/
  --exclude ai/detection/data/
  --exclude ai/detection/outputs/
  --exclude ai/segmentation/data/
  --exclude ai/segmentation/outputs/
  --exclude ai/classification/data/
  --exclude ai/classification/outputs/
  # Bytecode / packaging noise
  --exclude */__pycache__/
  --exclude *.pyc
  --exclude *.egg-info/
  # Model weight dumps
  --exclude *.pt
  --exclude *.pth
  # Tooling caches that may appear under the package tree
  --exclude .pytest_cache/
  --exclude .mypy_cache/
  --exclude .ruff_cache/
  --exclude .ipynb_checkpoints/
  --exclude htmlcov/
  --exclude .coverage
)

# Seed the stage at configure time so install(DIRECTORY) has a source.
file(MAKE_DIRECTORY "${_NECTAR_PY_STAGE}")
execute_process(
  COMMAND
    ${RSYNC_EXECUTABLE} -a --delete
    ${_NECTAR_PY_RSYNC_EXCLUDES}
    "${CMAKE_CURRENT_SOURCE_DIR}/nectar/"
    "${_NECTAR_PY_STAGE}/"
  RESULT_VARIABLE _nectar_rsync_rc
  ERROR_VARIABLE _nectar_rsync_err
)
if(NOT _nectar_rsync_rc EQUAL 0)
  message(FATAL_ERROR "Failed to stage nectar Python package: ${_nectar_rsync_err}")
endif()

# Refresh before every build so source edits reach install without bulk/cache dirs.
add_custom_target(nectar_python_stage ALL
  COMMAND
    ${RSYNC_EXECUTABLE} -a --delete
    ${_NECTAR_PY_RSYNC_EXCLUDES}
    "${CMAKE_CURRENT_SOURCE_DIR}/nectar/"
    "${_NECTAR_PY_STAGE}/"
  COMMENT "Staging nectar Python package (excluding datasets, outputs, caches)"
  VERBATIM
)

ament_python_install_package(${PROJECT_NAME}
  PACKAGE_DIR "${_NECTAR_PY_STAGE}"
)

# Ensure ament's egg copy/symlink runs after the stage is refreshed.
if(TARGET ament_cmake_python_symlink_nectar)
  add_dependencies(ament_cmake_python_symlink_nectar nectar_python_stage)
elseif(TARGET ament_cmake_python_copy_nectar)
  add_dependencies(ament_cmake_python_copy_nectar nectar_python_stage)
endif()

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
