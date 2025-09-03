// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from mirela_interfaces:msg/LineInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__STRUCT_H_
#define MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

/// Struct defined in msg/LineInfo in the package mirela_interfaces.
typedef struct mirela_interfaces__msg__LineInfo
{
  double center_x;
  double center_y;
  double angle;
  double width;
  double height;
} mirela_interfaces__msg__LineInfo;

// Struct for a sequence of mirela_interfaces__msg__LineInfo.
typedef struct mirela_interfaces__msg__LineInfo__Sequence
{
  mirela_interfaces__msg__LineInfo * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} mirela_interfaces__msg__LineInfo__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__STRUCT_H_
