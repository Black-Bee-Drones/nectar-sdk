// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from mirela_interfaces:msg/LineInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__TRAITS_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "mirela_interfaces/msg/detail/line_info__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace mirela_interfaces
{

namespace msg
{

inline void to_flow_style_yaml(
  const LineInfo & msg,
  std::ostream & out)
{
  out << "{";
  // member: center_x
  {
    out << "center_x: ";
    rosidl_generator_traits::value_to_yaml(msg.center_x, out);
    out << ", ";
  }

  // member: center_y
  {
    out << "center_y: ";
    rosidl_generator_traits::value_to_yaml(msg.center_y, out);
    out << ", ";
  }

  // member: angle
  {
    out << "angle: ";
    rosidl_generator_traits::value_to_yaml(msg.angle, out);
    out << ", ";
  }

  // member: width
  {
    out << "width: ";
    rosidl_generator_traits::value_to_yaml(msg.width, out);
    out << ", ";
  }

  // member: height
  {
    out << "height: ";
    rosidl_generator_traits::value_to_yaml(msg.height, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const LineInfo & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: center_x
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "center_x: ";
    rosidl_generator_traits::value_to_yaml(msg.center_x, out);
    out << "\n";
  }

  // member: center_y
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "center_y: ";
    rosidl_generator_traits::value_to_yaml(msg.center_y, out);
    out << "\n";
  }

  // member: angle
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "angle: ";
    rosidl_generator_traits::value_to_yaml(msg.angle, out);
    out << "\n";
  }

  // member: width
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "width: ";
    rosidl_generator_traits::value_to_yaml(msg.width, out);
    out << "\n";
  }

  // member: height
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "height: ";
    rosidl_generator_traits::value_to_yaml(msg.height, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const LineInfo & msg, bool use_flow_style = false)
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
  const mirela_interfaces::msg::LineInfo & msg,
  std::ostream & out, size_t indentation = 0)
{
  mirela_interfaces::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use mirela_interfaces::msg::to_yaml() instead")]]
inline std::string to_yaml(const mirela_interfaces::msg::LineInfo & msg)
{
  return mirela_interfaces::msg::to_yaml(msg);
}

template<>
inline const char * data_type<mirela_interfaces::msg::LineInfo>()
{
  return "mirela_interfaces::msg::LineInfo";
}

template<>
inline const char * name<mirela_interfaces::msg::LineInfo>()
{
  return "mirela_interfaces/msg/LineInfo";
}

template<>
struct has_fixed_size<mirela_interfaces::msg::LineInfo>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<mirela_interfaces::msg::LineInfo>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<mirela_interfaces::msg::LineInfo>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__TRAITS_HPP_
