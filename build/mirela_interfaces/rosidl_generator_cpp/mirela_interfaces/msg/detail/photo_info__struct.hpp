// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice

#ifndef MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__STRUCT_HPP_
#define MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__mirela_interfaces__msg__PhotoInfo __attribute__((deprecated))
#else
# define DEPRECATED__mirela_interfaces__msg__PhotoInfo __declspec(deprecated)
#endif

namespace mirela_interfaces
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct PhotoInfo_
{
  using Type = PhotoInfo_<ContainerAllocator>;

  explicit PhotoInfo_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->photo_num = "";
    }
  }

  explicit PhotoInfo_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : photo_num(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->photo_num = "";
    }
  }

  // field types and members
  using _coordinates_type =
    std::vector<double, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<double>>;
  _coordinates_type coordinates;
  using _photo_num_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _photo_num_type photo_num;

  // setters for named parameter idiom
  Type & set__coordinates(
    const std::vector<double, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<double>> & _arg)
  {
    this->coordinates = _arg;
    return *this;
  }
  Type & set__photo_num(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->photo_num = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    mirela_interfaces::msg::PhotoInfo_<ContainerAllocator> *;
  using ConstRawPtr =
    const mirela_interfaces::msg::PhotoInfo_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      mirela_interfaces::msg::PhotoInfo_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      mirela_interfaces::msg::PhotoInfo_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__mirela_interfaces__msg__PhotoInfo
    std::shared_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__mirela_interfaces__msg__PhotoInfo
    std::shared_ptr<mirela_interfaces::msg::PhotoInfo_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const PhotoInfo_ & other) const
  {
    if (this->coordinates != other.coordinates) {
      return false;
    }
    if (this->photo_num != other.photo_num) {
      return false;
    }
    return true;
  }
  bool operator!=(const PhotoInfo_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct PhotoInfo_

// alias to use template instance with default allocator
using PhotoInfo =
  mirela_interfaces::msg::PhotoInfo_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace mirela_interfaces

#endif  // MIRELA_INTERFACES__MSG__DETAIL__PHOTO_INFO__STRUCT_HPP_
