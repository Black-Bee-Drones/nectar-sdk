// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from mirela_interfaces:msg/LineInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__STRUCT_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__mirela_interfaces__msg__LineInfo __attribute__((deprecated))
#else
# define DEPRECATED__mirela_interfaces__msg__LineInfo __declspec(deprecated)
#endif

namespace mirela_interfaces
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct LineInfo_
{
  using Type = LineInfo_<ContainerAllocator>;

  explicit LineInfo_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->center_x = 0.0;
      this->center_y = 0.0;
      this->angle = 0.0;
      this->width = 0.0;
      this->height = 0.0;
    }
  }

  explicit LineInfo_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    (void)_alloc;
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->center_x = 0.0;
      this->center_y = 0.0;
      this->angle = 0.0;
      this->width = 0.0;
      this->height = 0.0;
    }
  }

  // field types and members
  using _center_x_type =
    double;
  _center_x_type center_x;
  using _center_y_type =
    double;
  _center_y_type center_y;
  using _angle_type =
    double;
  _angle_type angle;
  using _width_type =
    double;
  _width_type width;
  using _height_type =
    double;
  _height_type height;

  // setters for named parameter idiom
  Type & set__center_x(
    const double & _arg)
  {
    this->center_x = _arg;
    return *this;
  }
  Type & set__center_y(
    const double & _arg)
  {
    this->center_y = _arg;
    return *this;
  }
  Type & set__angle(
    const double & _arg)
  {
    this->angle = _arg;
    return *this;
  }
  Type & set__width(
    const double & _arg)
  {
    this->width = _arg;
    return *this;
  }
  Type & set__height(
    const double & _arg)
  {
    this->height = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    mirela_interfaces::msg::LineInfo_<ContainerAllocator> *;
  using ConstRawPtr =
    const mirela_interfaces::msg::LineInfo_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      mirela_interfaces::msg::LineInfo_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      mirela_interfaces::msg::LineInfo_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__mirela_interfaces__msg__LineInfo
    std::shared_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__mirela_interfaces__msg__LineInfo
    std::shared_ptr<mirela_interfaces::msg::LineInfo_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const LineInfo_ & other) const
  {
    if (this->center_x != other.center_x) {
      return false;
    }
    if (this->center_y != other.center_y) {
      return false;
    }
    if (this->angle != other.angle) {
      return false;
    }
    if (this->width != other.width) {
      return false;
    }
    if (this->height != other.height) {
      return false;
    }
    return true;
  }
  bool operator!=(const LineInfo_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct LineInfo_

// alias to use template instance with default allocator
using LineInfo =
  mirela_interfaces::msg::LineInfo_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace mirela_interfaces

#endif  // MIRELA_INTERFACES__MSG__DETAIL__LINE_INFO__STRUCT_HPP_
