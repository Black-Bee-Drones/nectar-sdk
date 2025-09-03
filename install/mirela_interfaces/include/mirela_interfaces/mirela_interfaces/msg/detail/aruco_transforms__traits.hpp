// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__TRAITS_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "mirela_interfaces/msg/detail/aruco_transforms__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'translation'
#include "geometry_msgs/msg/detail/vector3__traits.hpp"
// Member 'yaw'
#include "std_msgs/msg/detail/float64__traits.hpp"

namespace mirela_interfaces
{

namespace msg
{

inline void to_flow_style_yaml(
  const ArucoTransforms & msg,
  std::ostream & out)
{
  out << "{";
  // member: id
  {
    out << "id: ";
    rosidl_generator_traits::value_to_yaml(msg.id, out);
    out << ", ";
  }

  // member: translation
  {
    out << "translation: ";
    to_flow_style_yaml(msg.translation, out);
    out << ", ";
  }

  // member: yaw
  {
    out << "yaw: ";
    to_flow_style_yaml(msg.yaw, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const ArucoTransforms & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "id: ";
    rosidl_generator_traits::value_to_yaml(msg.id, out);
    out << "\n";
  }

  // member: translation
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "translation:\n";
    to_block_style_yaml(msg.translation, out, indentation + 2);
  }

  // member: yaw
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "yaw:\n";
    to_block_style_yaml(msg.yaw, out, indentation + 2);
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const ArucoTransforms & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace msg

}  // namespace mirela_interfaces

namespace rosidl_generator_traits
{

[[deprecated("use mirela_interfaces::msg::to_block_style_yaml() instead")]]
inline void to_yaml(
  const mirela_interfaces::msg::ArucoTransforms & msg,
  std::ostream & out, size_t indentation = 0)
{
  mirela_interfaces::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use mirela_interfaces::msg::to_yaml() instead")]]
inline std::string to_yaml(const mirela_interfaces::msg::ArucoTransforms & msg)
{
  return mirela_interfaces::msg::to_yaml(msg);
}

template<>
inline const char * data_type<mirela_interfaces::msg::ArucoTransforms>()
{
  return "mirela_interfaces::msg::ArucoTransforms";
}

template<>
inline const char * name<mirela_interfaces::msg::ArucoTransforms>()
{
  return "mirela_interfaces/msg/ArucoTransforms";
}

template<>
struct has_fixed_size<mirela_interfaces::msg::ArucoTransforms>
  : std::integral_constant<bool, has_fixed_size<geometry_msgs::msg::Vector3>::value && has_fixed_size<std_msgs::msg::Float64>::value> {};

template<>
struct has_bounded_size<mirela_interfaces::msg::ArucoTransforms>
  : std::integral_constant<bool, has_bounded_size<geometry_msgs::msg::Vector3>::value && has_bounded_size<std_msgs::msg::Float64>::value> {};

template<>
struct is_message<mirela_interfaces::msg::ArucoTransforms>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__TRAITS_HPP_
