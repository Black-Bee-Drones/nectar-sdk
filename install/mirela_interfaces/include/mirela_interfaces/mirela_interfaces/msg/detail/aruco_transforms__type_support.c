// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "mirela_interfaces/msg/detail/aruco_transforms__rosidl_typesupport_introspection_c.h"
#include "mirela_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "mirela_interfaces/msg/detail/aruco_transforms__functions.h"
#include "mirela_interfaces/msg/detail/aruco_transforms__struct.h"


// Include directives for member types
// Member `translation`
#include "geometry_msgs/msg/vector3.h"
// Member `translation`
#include "geometry_msgs/msg/detail/vector3__rosidl_typesupport_introspection_c.h"
// Member `yaw`
#include "std_msgs/msg/float64.h"
// Member `yaw`
#include "std_msgs/msg/detail/float64__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  mirela_interfaces__msg__ArucoTransforms__init(message_memory);
}

void mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_fini_function(void * message_memory)
{
  mirela_interfaces__msg__ArucoTransforms__fini(message_memory);
}

static rosidl_typesupport_introspection_c__MessageMember mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_member_array[3] = {
  {
    "id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__ArucoTransforms, id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "translation",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__ArucoTransforms, translation),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "yaw",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__ArucoTransforms, yaw),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_members = {
  "mirela_interfaces__msg",  // message namespace
  "ArucoTransforms",  // message name
  3,  // number of fields
  sizeof(mirela_interfaces__msg__ArucoTransforms),
  mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_member_array,  // message members
  mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_init_function,  // function to initialize message memory (memory has to be allocated)
  mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_type_support_handle = {
  0,
  &mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_mirela_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, mirela_interfaces, msg, ArucoTransforms)() {
  mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_member_array[1].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, geometry_msgs, msg, Vector3)();
  mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_member_array[2].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, std_msgs, msg, Float64)();
  if (!mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_type_support_handle.typesupport_identifier) {
    mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &mirela_interfaces__msg__ArucoTransforms__rosidl_typesupport_introspection_c__ArucoTransforms_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
