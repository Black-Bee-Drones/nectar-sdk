// generated from rosidl_typesupport_fastrtps_c/resource/idl__type_support_c.cpp.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice
#include "mirela_interfaces/msg/detail/photo_info__rosidl_typesupport_fastrtps_c.h"


#include <cassert>
#include <limits>
#include <string>
#include "rosidl_typesupport_fastrtps_c/identifier.h"
#include "rosidl_typesupport_fastrtps_c/wstring_conversion.hpp"
#include "rosidl_typesupport_fastrtps_cpp/message_type_support.h"
#include "mirela_interfaces/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "mirela_interfaces/msg/detail/photo_info__struct.h"
#include "mirela_interfaces/msg/detail/photo_info__functions.h"
#include "fastcdr/Cdr.h"

#ifndef _WIN32
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wunused-parameter"
# ifdef __clang__
#  pragma clang diagnostic ignored "-Wdeprecated-register"
#  pragma clang diagnostic ignored "-Wreturn-type-c-linkage"
# endif
#endif
#ifndef _WIN32
# pragma GCC diagnostic pop
#endif

// includes and forward declarations of message dependencies and their conversion functions

#if defined(__cplusplus)
extern "C"
{
#endif

#include "rosidl_runtime_c/primitives_sequence.h"  // coordinates
#include "rosidl_runtime_c/primitives_sequence_functions.h"  // coordinates
#include "rosidl_runtime_c/string.h"  // photo_num
#include "rosidl_runtime_c/string_functions.h"  // photo_num

// forward declare type support functions


using _PhotoInfo__ros_msg_type = mirela_interfaces__msg__PhotoInfo;

static bool _PhotoInfo__cdr_serialize(
  const void * untyped_ros_message,
  eprosima::fastcdr::Cdr & cdr)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  const _PhotoInfo__ros_msg_type * ros_message = static_cast<const _PhotoInfo__ros_msg_type *>(untyped_ros_message);
  // Field name: coordinates
  {
    size_t size = ros_message->coordinates.size;
    auto array_ptr = ros_message->coordinates.data;
    cdr << static_cast<uint32_t>(size);
    cdr.serializeArray(array_ptr, size);
  }

  // Field name: photo_num
  {
    const rosidl_runtime_c__String * str = &ros_message->photo_num;
    if (str->capacity == 0 || str->capacity <= str->size) {
      fprintf(stderr, "string capacity not greater than size\n");
      return false;
    }
    if (str->data[str->size] != '\0') {
      fprintf(stderr, "string not null-terminated\n");
      return false;
    }
    cdr << str->data;
  }

  return true;
}

static bool _PhotoInfo__cdr_deserialize(
  eprosima::fastcdr::Cdr & cdr,
  void * untyped_ros_message)
{
  if (!untyped_ros_message) {
    fprintf(stderr, "ros message handle is null\n");
    return false;
  }
  _PhotoInfo__ros_msg_type * ros_message = static_cast<_PhotoInfo__ros_msg_type *>(untyped_ros_message);
  // Field name: coordinates
  {
    uint32_t cdrSize;
    cdr >> cdrSize;
    size_t size = static_cast<size_t>(cdrSize);
    if (ros_message->coordinates.data) {
      rosidl_runtime_c__double__Sequence__fini(&ros_message->coordinates);
    }
    if (!rosidl_runtime_c__double__Sequence__init(&ros_message->coordinates, size)) {
      fprintf(stderr, "failed to create array for field 'coordinates'");
      return false;
    }
    auto array_ptr = ros_message->coordinates.data;
    cdr.deserializeArray(array_ptr, size);
  }

  // Field name: photo_num
  {
    std::string tmp;
    cdr >> tmp;
    if (!ros_message->photo_num.data) {
      rosidl_runtime_c__String__init(&ros_message->photo_num);
    }
    bool succeeded = rosidl_runtime_c__String__assign(
      &ros_message->photo_num,
      tmp.c_str());
    if (!succeeded) {
      fprintf(stderr, "failed to assign string into field 'photo_num'\n");
      return false;
    }
  }

  return true;
}  // NOLINT(readability/fn_size)

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_mirela_interfaces
size_t get_serialized_size_mirela_interfaces__msg__PhotoInfo(
  const void * untyped_ros_message,
  size_t current_alignment)
{
  const _PhotoInfo__ros_msg_type * ros_message = static_cast<const _PhotoInfo__ros_msg_type *>(untyped_ros_message);
  (void)ros_message;
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  (void)padding;
  (void)wchar_size;

  // field.name coordinates
  {
    size_t array_size = ros_message->coordinates.size;
    auto array_ptr = ros_message->coordinates.data;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);
    (void)array_ptr;
    size_t item_size = sizeof(array_ptr[0]);
    current_alignment += array_size * item_size +
      eprosima::fastcdr::Cdr::alignment(current_alignment, item_size);
  }
  // field.name photo_num
  current_alignment += padding +
    eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
    (ros_message->photo_num.size + 1);

  return current_alignment - initial_alignment;
}

static uint32_t _PhotoInfo__get_serialized_size(const void * untyped_ros_message)
{
  return static_cast<uint32_t>(
    get_serialized_size_mirela_interfaces__msg__PhotoInfo(
      untyped_ros_message, 0));
}

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_mirela_interfaces
size_t max_serialized_size_mirela_interfaces__msg__PhotoInfo(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment)
{
  size_t initial_alignment = current_alignment;

  const size_t padding = 4;
  const size_t wchar_size = 4;
  size_t last_member_size = 0;
  (void)last_member_size;
  (void)padding;
  (void)wchar_size;

  full_bounded = true;
  is_plain = true;

  // member: coordinates
  {
    size_t array_size = 0;
    full_bounded = false;
    is_plain = false;
    current_alignment += padding +
      eprosima::fastcdr::Cdr::alignment(current_alignment, padding);

    last_member_size = array_size * sizeof(uint64_t);
    current_alignment += array_size * sizeof(uint64_t) +
      eprosima::fastcdr::Cdr::alignment(current_alignment, sizeof(uint64_t));
  }
  // member: photo_num
  {
    size_t array_size = 1;

    full_bounded = false;
    is_plain = false;
    for (size_t index = 0; index < array_size; ++index) {
      current_alignment += padding +
        eprosima::fastcdr::Cdr::alignment(current_alignment, padding) +
        1;
    }
  }

  size_t ret_val = current_alignment - initial_alignment;
  if (is_plain) {
    // All members are plain, and type is not empty.
    // We still need to check that the in-memory alignment
    // is the same as the CDR mandated alignment.
    using DataType = mirela_interfaces__msg__PhotoInfo;
    is_plain =
      (
      offsetof(DataType, photo_num) +
      last_member_size
      ) == ret_val;
  }

  return ret_val;
}

static size_t _PhotoInfo__max_serialized_size(char & bounds_info)
{
  bool full_bounded;
  bool is_plain;
  size_t ret_val;

  ret_val = max_serialized_size_mirela_interfaces__msg__PhotoInfo(
    full_bounded, is_plain, 0);

  bounds_info =
    is_plain ? ROSIDL_TYPESUPPORT_FASTRTPS_PLAIN_TYPE :
    full_bounded ? ROSIDL_TYPESUPPORT_FASTRTPS_BOUNDED_TYPE : ROSIDL_TYPESUPPORT_FASTRTPS_UNBOUNDED_TYPE;
  return ret_val;
}


static message_type_support_callbacks_t __callbacks_PhotoInfo = {
  "mirela_interfaces::msg",
  "PhotoInfo",
  _PhotoInfo__cdr_serialize,
  _PhotoInfo__cdr_deserialize,
  _PhotoInfo__get_serialized_size,
  _PhotoInfo__max_serialized_size
};

static rosidl_message_type_support_t _PhotoInfo__type_support = {
  rosidl_typesupport_fastrtps_c__identifier,
  &__callbacks_PhotoInfo,
  get_message_typesupport_handle_function,
};

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, mirela_interfaces, msg, PhotoInfo)() {
  return &_PhotoInfo__type_support;
}

#if defined(__cplusplus)
}
#endif
