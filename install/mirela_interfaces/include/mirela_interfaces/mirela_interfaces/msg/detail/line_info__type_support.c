// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from mirela_interfaces:msg/LineInfo.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "mirela_interfaces/msg/detail/line_info__rosidl_typesupport_introspection_c.h"
#include "mirela_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "mirela_interfaces/msg/detail/line_info__functions.h"
#include "mirela_interfaces/msg/detail/line_info__struct.h"


#ifdef __cplusplus
extern "C"
{
#endif

void mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  mirela_interfaces__msg__LineInfo__init(message_memory);
}

void mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_fini_function(void * message_memory)
{
  mirela_interfaces__msg__LineInfo__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_member_array[5] = {
  {
    "center_x",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__LineInfo, center_x),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "center_y",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__LineInfo, center_y),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "angle",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__LineInfo, angle),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "width",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__LineInfo, width),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "height",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__LineInfo, height),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_members = {
  "mirela_interfaces__msg",  // message namespace
  "LineInfo",  // message name
  5,  // number of fields
  sizeof(mirela_interfaces__msg__LineInfo),
  mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_member_array,  // message members
  mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_init_function,  // function to initialize message memory (memory has to be allocated)
  mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_type_support_handle = {
  0,
  &mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_mirela_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, mirela_interfaces, msg, LineInfo)() {
  if (!mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_type_support_handle.typesupport_identifier) {
    mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &mirela_interfaces__msg__LineInfo__rosidl_typesupport_introspection_c__LineInfo_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
