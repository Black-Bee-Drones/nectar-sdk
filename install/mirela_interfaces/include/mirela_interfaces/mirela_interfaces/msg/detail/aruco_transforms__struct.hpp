// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__STRUCT_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


// Include directives for member types
// Member 'translation'
#include "geometry_msgs/msg/detail/vector3__struct.hpp"
// Member 'yaw'
#include "std_msgs/msg/detail/float64__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__mirela_interfaces__msg__ArucoTransforms __attribute__((deprecated))
#else
# define DEPRECATED__mirela_interfaces__msg__ArucoTransforms __declspec(deprecated)
#endif

namespace mirela_interfaces
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct ArucoTransforms_
{
  using Type = ArucoTransforms_<ContainerAllocator>;

  explicit ArucoTransforms_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : translation(_init),
    yaw(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->id = 0l;
    }
  }

  explicit ArucoTransforms_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : translation(_alloc, _init),
    yaw(_alloc, _init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->id = 0l;
    }
  }

  // field types and members
  using _id_type =
    int32_t;
  _id_type id;
  using _translation_type =
    geometry_msgs::msg::Vector3_<ContainerAllocator>;
  _translation_type translation;
  using _yaw_type =
    std_msgs::msg::Float64_<ContainerAllocator>;
  _yaw_type yaw;

  // setters for named parameter idiom
  Type & set__id(
    const int32_t & _arg)
  {
    this->id = _arg;
    return *this;
  }
  Type & set__translation(
    const geometry_msgs::msg::Vector3_<ContainerAllocator> & _arg)
  {
    this->translation = _arg;
    return *this;
  }
  Type & set__yaw(
    const std_msgs::msg::Float64_<ContainerAllocator> & _arg)
  {
    this->yaw = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator> *;
  using ConstRawPtr =
    const mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__mirela_interfaces__msg__ArucoTransforms
    std::shared_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__mirela_interfaces__msg__ArucoTransforms
    std::shared_ptr<mirela_interfaces::msg::ArucoTransforms_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const ArucoTransforms_ & other) const
  {
    if (this->id != other.id) {
      return false;
    }
    if (this->translation != other.translation) {
      return false;
    }
    if (this->yaw != other.yaw) {
      return false;
    }
    return true;
  }
  bool operator!=(const ArucoTransforms_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct ArucoTransforms_

// alias to use template instance with default allocator
using ArucoTransforms =
  mirela_interfaces::msg::ArucoTransforms_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace mirela_interfaces

#endif  // MIRELA_INTERFACES__MSG__DETAIL__ARUCO_TRANSFORMS__STRUCT_HPP_
