// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__BUILDER_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "mirela_interfaces/msg/detail/aruco_transforms__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace mirela_interfaces
{

namespace msg
{

namespace builder
{

class Init_ArucoTransforms_yaw
{
public:
  explicit Init_ArucoTransforms_yaw(::mirela_interfaces::msg::ArucoTransforms & msg)
  : msg_(msg)
  {}
  ::mirela_interfaces::msg::ArucoTransforms yaw(::mirela_interfaces::msg::ArucoTransforms::_yaw_type arg)
  {
    msg_.yaw = std::move(arg);
    return std::move(msg_);
  }

private:
  ::mirela_interfaces::msg::ArucoTransforms msg_;
};

class Init_ArucoTransforms_translation
{
public:
  explicit Init_ArucoTransforms_translation(::mirela_interfaces::msg::ArucoTransforms & msg)
  : msg_(msg)
  {}
  Init_ArucoTransforms_yaw translation(::mirela_interfaces::msg::ArucoTransforms::_translation_type arg)
  {
    msg_.translation = std::move(arg);
    return Init_ArucoTransforms_yaw(msg_);
  }

private:
  ::mirela_interfaces::msg::ArucoTransforms msg_;
};

class Init_ArucoTransforms_id
{
public:
  Init_ArucoTransforms_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_ArucoTransforms_translation id(::mirela_interfaces::msg::ArucoTransforms::_id_type arg)
  {
    msg_.id = std::move(arg);
    return Init_ArucoTransforms_translation(msg_);
  }

private:
  ::mirela_interfaces::msg::ArucoTransforms msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::mirela_interfaces::msg::ArucoTransforms>()
{
  return mirela_interfaces::msg::builder::Init_ArucoTransforms_id();
}

}  // namespace mirela_interfaces

#endif  // MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__BUILDER_HPP_
