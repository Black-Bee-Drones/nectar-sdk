// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__STRUCT_H_
#define MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'translation'
#include "geometry_msgs/msg/detail/vector3__struct.h"
// Member 'yaw'
#include "std_msgs/msg/detail/float64__struct.h"

/// Struct defined in msg/ArucoTransforms in the package mirela_interfaces.
typedef struct mirela_interfaces__msg__ArucoTransforms
{
  int32_t id;
  geometry_msgs__msg__Vector3 translation;
  std_msgs__msg__Float64 yaw;
} mirela_interfaces__msg__ArucoTransforms;

// Struct for a sequence of mirela_interfaces__msg__ArucoTransforms.
typedef struct mirela_interfaces__msg__ArucoTransforms__Sequence
{
  mirela_interfaces__msg__ArucoTransforms * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} mirela_interfaces__msg__ArucoTransforms__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__STRUCT_H_
