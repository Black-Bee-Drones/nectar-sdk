// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "mirela_interfaces/msg/detail/photo_info__rosidl_typesupport_introspection_c.h"
#include "mirela_interfaces/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "mirela_interfaces/msg/detail/photo_info__functions.h"
#include "mirela_interfaces/msg/detail/photo_info__struct.h"


// Include directives for member types
// Member `coordinates`
#include "rosidl_runtime_c/primitives_sequence_functions.h"
// Member `photo_num`
#include "rosidl_runtime_c/string_functions.h"

#ifdef __cplusplus
extern "C"
{
#endif

void mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  mirela_interfaces__msg__PhotoInfo__init(message_memory);
}

void mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_fini_function(void * message_memory)
{
  mirela_interfaces__msg__PhotoInfo__fini(message_memory);
}

size_t mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__size_function__PhotoInfo__coordinates(
  const void * untyped_member)
{
  const rosidl_runtime_c__double__Sequence * member =
    (const rosidl_runtime_c__double__Sequence *)(untyped_member);
  return member->size;
}

const void * mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__get_const_function__PhotoInfo__coordinates(
  const void * untyped_member, size_t index)
{
  const rosidl_runtime_c__double__Sequence * member =
    (const rosidl_runtime_c__double__Sequence *)(untyped_member);
  return &member->data[index];
}

void * mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__get_function__PhotoInfo__coordinates(
  void * untyped_member, size_t index)
{
  rosidl_runtime_c__double__Sequence * member =
    (rosidl_runtime_c__double__Sequence *)(untyped_member);
  return &member->data[index];
}

void mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__fetch_function__PhotoInfo__coordinates(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const double * item =
    ((const double *)
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__get_const_function__PhotoInfo__coordinates(untyped_member, index));
  double * value =
    (double *)(untyped_value);
  *value = *item;
}

void mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__assign_function__PhotoInfo__coordinates(
  void * untyped_member, size_t index, const void * untyped_value)
{
  double * item =
    ((double *)
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__get_function__PhotoInfo__coordinates(untyped_member, index));
  const double * value =
    (const double *)(untyped_value);
  *item = *value;
}

bool mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__resize_function__PhotoInfo__coordinates(
  void * untyped_member, size_t size)
{
  rosidl_runtime_c__double__Sequence * member =
    (rosidl_runtime_c__double__Sequence *)(untyped_member);
  rosidl_runtime_c__double__Sequence__fini(member);
  return rosidl_runtime_c__double__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_member_array[2] = {
  {
    "coordinates",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__PhotoInfo, coordinates),  // bytes offset in struct
    NULL,  // default value
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__size_function__PhotoInfo__coordinates,  // size() function pointer
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__get_const_function__PhotoInfo__coordinates,  // get_const(index) function pointer
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__get_function__PhotoInfo__coordinates,  // get(index) function pointer
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__fetch_function__PhotoInfo__coordinates,  // fetch(index, &value) function pointer
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__assign_function__PhotoInfo__coordinates,  // assign(index, value) function pointer
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__resize_function__PhotoInfo__coordinates  // resize(index) function pointer
  },
  {
    "photo_num",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces__msg__PhotoInfo, photo_num),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_members = {
  "mirela_interfaces__msg",  // message namespace
  "PhotoInfo",  // message name
  2,  // number of fields
  sizeof(mirela_interfaces__msg__PhotoInfo),
  mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_member_array,  // message members
  mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_init_function,  // function to initialize message memory (memory has to be allocated)
  mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_type_support_handle = {
  0,
  &mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_members,
  get_message_typesupport_handle_function,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_mirela_interfaces
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, mirela_interfaces, msg, PhotoInfo)() {
  if (!mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_type_support_handle.typesupport_identifier) {
    mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &mirela_interfaces__msg__PhotoInfo__rosidl_typesupport_introspection_c__PhotoInfo_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
