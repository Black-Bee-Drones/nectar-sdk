// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__STRUCT_H_
#define MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'coordinates'
#include "rosidl_runtime_c/primitives_sequence.h"
// Member 'photo_num'
#include "rosidl_runtime_c/string.h"

/// Struct defined in msg/PhotoInfo in the package mirela_interfaces.
typedef struct mirela_interfaces__msg__PhotoInfo
{
  rosidl_runtime_c__double__Sequence coordinates;
  rosidl_runtime_c__String photo_num;
} mirela_interfaces__msg__PhotoInfo;

// Struct for a sequence of mirela_interfaces__msg__PhotoInfo.
typedef struct mirela_interfaces__msg__PhotoInfo__Sequence
{
  mirela_interfaces__msg__PhotoInfo * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} mirela_interfaces__msg__PhotoInfo__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__STRUCT_H_
