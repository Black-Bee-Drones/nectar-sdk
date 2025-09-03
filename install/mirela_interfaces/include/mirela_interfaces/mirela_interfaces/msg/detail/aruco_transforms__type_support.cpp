// generated from rosidl_typesupport_introspection_cpp/resource/idl__type_support.cpp.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice

#include "array"
#include "cstddef"
#include "string"
#include "vector"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_cpp/message_type_support.hpp"
#include "rosidl_typesupport_interface/macros.h"
#include "mirela_interfaces/msg/detail/aruco_transforms__struct.hpp"
#include "rosidl_typesupport_introspection_cpp/field_types.hpp"
#include "rosidl_typesupport_introspection_cpp/identifier.hpp"
#include "rosidl_typesupport_introspection_cpp/message_introspection.hpp"
#include "rosidl_typesupport_introspection_cpp/message_type_support_decl.hpp"
#include "rosidl_typesupport_introspection_cpp/visibility_control.h"

namespace mirela_interfaces
{

namespace msg
{

namespace rosidl_typesupport_introspection_cpp
{

void ArucoTransforms_init_function(
  void * message_memory, rosidl_runtime_cpp::MessageInitialization _init)
{
  new (message_memory) mirela_interfaces::msg::ArucoTransforms(_init);
}

void ArucoTransforms_fini_function(void * message_memory)
{
  auto typed_message = static_cast<mirela_interfaces::msg::ArucoTransforms *>(message_memory);
  typed_message->~ArucoTransforms();
}

static const ::rosidl_typesupport_introspection_cpp::MessageMember ArucoTransforms_message_member_array[3] = {
  {
    "id",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_INT32,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces::msg::ArucoTransforms, id),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "translation",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<geometry_msgs::msg::Vector3>(),  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces::msg::ArucoTransforms, translation),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "yaw",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<std_msgs::msg::Float64>(),  // members of sub message
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(mirela_interfaces::msg::ArucoTransforms, yaw),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  }
};

static const ::rosidl_typesupport_introspection_cpp::MessageMembers ArucoTransforms_message_members = {
  "mirela_interfaces::msg",  // message namespace
  "ArucoTransforms",  // message name
  3,  // number of fields
  sizeof(mirela_interfaces::msg::ArucoTransforms),
  ArucoTransforms_message_member_array,  // message members
  ArucoTransforms_init_function,  // function to initialize message memory (memory has to be allocated)
  ArucoTransforms_fini_function  // function to terminate message instance (will not free memory)
};

static const rosidl_message_type_support_t ArucoTransforms_message_type_support_handle = {
  ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  &ArucoTransforms_message_members,
  get_message_typesupport_handle_function,
};

}  // namespace rosidl_typesupport_introspection_cpp

}  // namespace msg

}  // namespace mirela_interfaces


namespace rosidl_typesupport_introspection_cpp
{

template<>
ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<mirela_interfaces::msg::ArucoTransforms>()
{
  return &::mirela_interfaces::msg::rosidl_typesupport_introspection_cpp::ArucoTransforms_message_type_support_handle;
}

}  // namespace rosidl_typesupport_introspection_cpp

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, mirela_interfaces, msg, ArucoTransforms)() {
  return &::mirela_interfaces::msg::rosidl_typesupport_introspection_cpp::ArucoTransforms_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif
