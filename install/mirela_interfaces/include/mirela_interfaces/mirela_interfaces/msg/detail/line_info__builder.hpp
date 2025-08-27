// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from mirela_interfaces:msg/LineInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__BUILDER_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "mirela_interfaces/msg/detail/line_info__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace mirela_interfaces
{

namespace msg
{

namespace builder
{

class Init_LineInfo_height
{
public:
  explicit Init_LineInfo_height(::mirela_interfaces::msg::LineInfo & msg)
  : msg_(msg)
  {}
  ::mirela_interfaces::msg::LineInfo height(::mirela_interfaces::msg::LineInfo::_height_type arg)
  {
    msg_.height = std::move(arg);
    return std::move(msg_);
  }

private:
  ::mirela_interfaces::msg::LineInfo msg_;
};

class Init_LineInfo_width
{
public:
  explicit Init_LineInfo_width(::mirela_interfaces::msg::LineInfo & msg)
  : msg_(msg)
  {}
  Init_LineInfo_height width(::mirela_interfaces::msg::LineInfo::_width_type arg)
  {
    msg_.width = std::move(arg);
    return Init_LineInfo_height(msg_);
  }

private:
  ::mirela_interfaces::msg::LineInfo msg_;
};

class Init_LineInfo_angle
{
public:
  explicit Init_LineInfo_angle(::mirela_interfaces::msg::LineInfo & msg)
  : msg_(msg)
  {}
  Init_LineInfo_width angle(::mirela_interfaces::msg::LineInfo::_angle_type arg)
  {
    msg_.angle = std::move(arg);
    return Init_LineInfo_width(msg_);
  }

private:
  ::mirela_interfaces::msg::LineInfo msg_;
};

class Init_LineInfo_center_y
{
public:
  explicit Init_LineInfo_center_y(::mirela_interfaces::msg::LineInfo & msg)
  : msg_(msg)
  {}
  Init_LineInfo_angle center_y(::mirela_interfaces::msg::LineInfo::_center_y_type arg)
  {
    msg_.center_y = std::move(arg);
    return Init_LineInfo_angle(msg_);
  }

private:
  ::mirela_interfaces::msg::LineInfo msg_;
};

class Init_LineInfo_center_x
{
public:
  Init_LineInfo_center_x()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_LineInfo_center_y center_x(::mirela_interfaces::msg::LineInfo::_center_x_type arg)
  {
    msg_.center_x = std::move(arg);
    return Init_LineInfo_center_y(msg_);
  }

private:
  ::mirela_interfaces::msg::LineInfo msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::mirela_interfaces::msg::LineInfo>()
{
  return mirela_interfaces::msg::builder::Init_LineInfo_center_x();
}

}  // namespace mirela_interfaces

#endif  // MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__BUILDER_HPP_
