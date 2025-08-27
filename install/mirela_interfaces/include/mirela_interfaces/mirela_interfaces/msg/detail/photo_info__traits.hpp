// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__TRAITS_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "mirela_interfaces/msg/detail/photo_info__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace mirela_interfaces
{

namespace msg
{

inline void to_flow_style_yaml(
  const PhotoInfo & msg,
  std::ostream & out)
{
  out << "{";
  // member: coordinates
  {
    if (msg.coordinates.size() == 0) {
      out << "coordinates: []";
    } else {
      out << "coordinates: [";
      size_t pending_items = msg.coordinates.size();
      for (auto item : msg.coordinates) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: photo_num
  {
    out << "photo_num: ";
    rosidl_generator_traits::value_to_yaml(msg.photo_num, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const PhotoInfo & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: coordinates
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.coordinates.size() == 0) {
      out << "coordinates: []\n";
    } else {
      out << "coordinates:\n";
      for (auto item : msg.coordinates) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: photo_num
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "photo_num: ";
    rosidl_generator_traits::value_to_yaml(msg.photo_num, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const PhotoInfo & msg, bool use_flow_style = false)
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
  const mirela_interfaces::msg::PhotoInfo & msg,
  std::ostream & out, size_t indentation = 0)
{
  mirela_interfaces::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use mirela_interfaces::msg::to_yaml() instead")]]
inline std::string to_yaml(const mirela_interfaces::msg::PhotoInfo & msg)
{
  return mirela_interfaces::msg::to_yaml(msg);
}

template<>
inline const char * data_type<mirela_interfaces::msg::PhotoInfo>()
{
  return "mirela_interfaces::msg::PhotoInfo";
}

template<>
inline const char * name<mirela_interfaces::msg::PhotoInfo>()
{
  return "mirela_interfaces/msg/PhotoInfo";
}

template<>
struct has_fixed_size<mirela_interfaces::msg::PhotoInfo>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<mirela_interfaces::msg::PhotoInfo>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<mirela_interfaces::msg::PhotoInfo>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__TRAITS_HPP_
