// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__BUILDER_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "mirela_interfaces/msg/detail/photo_info__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace mirela_interfaces
{

namespace msg
{

namespace builder
{

class Init_PhotoInfo_photo_num
{
public:
  explicit Init_PhotoInfo_photo_num(::mirela_interfaces::msg::PhotoInfo & msg)
  : msg_(msg)
  {}
  ::mirela_interfaces::msg::PhotoInfo photo_num(::mirela_interfaces::msg::PhotoInfo::_photo_num_type arg)
  {
    msg_.photo_num = std::move(arg);
    return std::move(msg_);
  }

private:
  ::mirela_interfaces::msg::PhotoInfo msg_;
};

class Init_PhotoInfo_coordinates
{
public:
  Init_PhotoInfo_coordinates()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_PhotoInfo_photo_num coordinates(::mirela_interfaces::msg::PhotoInfo::_coordinates_type arg)
  {
    msg_.coordinates = std::move(arg);
    return Init_PhotoInfo_photo_num(msg_);
  }

private:
  ::mirela_interfaces::msg::PhotoInfo msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::mirela_interfaces::msg::PhotoInfo>()
{
  return mirela_interfaces::msg::builder::Init_PhotoInfo_coordinates();
}

}  // namespace mirela_interfaces

#endif  // MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__BUILDER_HPP_
