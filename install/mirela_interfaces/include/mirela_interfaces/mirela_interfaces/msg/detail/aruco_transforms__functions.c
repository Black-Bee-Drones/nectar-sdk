// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from mirela_interfaces:msg/ArucoTransforms.idl
// generated code does not contain a copyright notice
#include "mirela_interfaces/msg/detail/aruco_transforms__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `translation`
#include "geometry_msgs/msg/detail/vector3__functions.h"
// Member `yaw`
#include "std_msgs/msg/detail/float64__functions.h"

bool
mirela_interfaces__msg__ArucoTransforms__init(mirela_interfaces__msg__ArucoTransforms * msg)
{
  if (!msg) {
    return false;
  }
  // id
  // translation
  if (!geometry_msgs__msg__Vector3__init(&msg->translation)) {
    mirela_interfaces__msg__ArucoTransforms__fini(msg);
    return false;
  }
  // yaw
  if (!std_msgs__msg__Float64__init(&msg->yaw)) {
    mirela_interfaces__msg__ArucoTransforms__fini(msg);
    return false;
  }
  return true;
}

void
mirela_interfaces__msg__ArucoTransforms__fini(mirela_interfaces__msg__ArucoTransforms * msg)
{
  if (!msg) {
    return;
  }
  // id
  // translation
  geometry_msgs__msg__Vector3__fini(&msg->translation);
  // yaw
  std_msgs__msg__Float64__fini(&msg->yaw);
}

bool
mirela_interfaces__msg__ArucoTransforms__are_equal(const mirela_interfaces__msg__ArucoTransforms * lhs, const mirela_interfaces__msg__ArucoTransforms * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // id
  if (lhs->id != rhs->id) {
    return false;
  }
  // translation
  if (!geometry_msgs__msg__Vector3__are_equal(
      &(lhs->translation), &(rhs->translation)))
  {
    return false;
  }
  // yaw
  if (!std_msgs__msg__Float64__are_equal(
      &(lhs->yaw), &(rhs->yaw)))
  {
    return false;
  }
  return true;
}

bool
mirela_interfaces__msg__ArucoTransforms__copy(
  const mirela_interfaces__msg__ArucoTransforms * input,
  mirela_interfaces__msg__ArucoTransforms * output)
{
  if (!input || !output) {
    return false;
  }
  // id
  output->id = input->id;
  // translation
  if (!geometry_msgs__msg__Vector3__copy(
      &(input->translation), &(output->translation)))
  {
    return false;
  }
  // yaw
  if (!std_msgs__msg__Float64__copy(
      &(input->yaw), &(output->yaw)))
  {
    return false;
  }
  return true;
}

mirela_interfaces__msg__ArucoTransforms *
mirela_interfaces__msg__ArucoTransforms__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__ArucoTransforms * msg = (mirela_interfaces__msg__ArucoTransforms *)allocator.allocate(sizeof(mirela_interfaces__msg__ArucoTransforms), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(mirela_interfaces__msg__ArucoTransforms));
  bool success = mirela_interfaces__msg__ArucoTransforms__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
mirela_interfaces__msg__ArucoTransforms__destroy(mirela_interfaces__msg__ArucoTransforms * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    mirela_interfaces__msg__ArucoTransforms__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
mirela_interfaces__msg__ArucoTransforms__Sequence__init(mirela_interfaces__msg__ArucoTransforms__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__ArucoTransforms * data = NULL;

  if (size) {
    data = (mirela_interfaces__msg__ArucoTransforms *)allocator.zero_allocate(size, sizeof(mirela_interfaces__msg__ArucoTransforms), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = mirela_interfaces__msg__ArucoTransforms__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        mirela_interfaces__msg__ArucoTransforms__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
mirela_interfaces__msg__ArucoTransforms__Sequence__fini(mirela_interfaces__msg__ArucoTransforms__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      mirela_interfaces__msg__ArucoTransforms__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

mirela_interfaces__msg__ArucoTransforms__Sequence *
mirela_interfaces__msg__ArucoTransforms__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__ArucoTransforms__Sequence * array = (mirela_interfaces__msg__ArucoTransforms__Sequence *)allocator.allocate(sizeof(mirela_interfaces__msg__ArucoTransforms__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = mirela_interfaces__msg__ArucoTransforms__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
mirela_interfaces__msg__ArucoTransforms__Sequence__destroy(mirela_interfaces__msg__ArucoTransforms__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    mirela_interfaces__msg__ArucoTransforms__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
mirela_interfaces__msg__ArucoTransforms__Sequence__are_equal(const mirela_interfaces__msg__ArucoTransforms__Sequence * lhs, const mirela_interfaces__msg__ArucoTransforms__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!mirela_interfaces__msg__ArucoTransforms__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
mirela_interfaces__msg__ArucoTransforms__Sequence__copy(
  const mirela_interfaces__msg__ArucoTransforms__Sequence * input,
  mirela_interfaces__msg__ArucoTransforms__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(mirela_interfaces__msg__ArucoTransforms);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    mirela_interfaces__msg__ArucoTransforms * data =
      (mirela_interfaces__msg__ArucoTransforms *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!mirela_interfaces__msg__ArucoTransforms__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          mirela_interfaces__msg__ArucoTransforms__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!mirela_interfaces__msg__ArucoTransforms__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
