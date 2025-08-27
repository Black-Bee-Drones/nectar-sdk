// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from mirela_interfaces:msg/PhotoInfo.idl
// generated code does not contain a copyright notice
#include "mirela_interfaces/msg/detail/photo_info__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `coordinates`
#include "rosidl_runtime_c/primitives_sequence_functions.h"
// Member `photo_num`
#include "rosidl_runtime_c/string_functions.h"

bool
mirela_interfaces__msg__PhotoInfo__init(mirela_interfaces__msg__PhotoInfo * msg)
{
  if (!msg) {
    return false;
  }
  // coordinates
  if (!rosidl_runtime_c__double__Sequence__init(&msg->coordinates, 0)) {
    mirela_interfaces__msg__PhotoInfo__fini(msg);
    return false;
  }
  // photo_num
  if (!rosidl_runtime_c__String__init(&msg->photo_num)) {
    mirela_interfaces__msg__PhotoInfo__fini(msg);
    return false;
  }
  return true;
}

void
mirela_interfaces__msg__PhotoInfo__fini(mirela_interfaces__msg__PhotoInfo * msg)
{
  if (!msg) {
    return;
  }
  // coordinates
  rosidl_runtime_c__double__Sequence__fini(&msg->coordinates);
  // photo_num
  rosidl_runtime_c__String__fini(&msg->photo_num);
}

bool
mirela_interfaces__msg__PhotoInfo__are_equal(const mirela_interfaces__msg__PhotoInfo * lhs, const mirela_interfaces__msg__PhotoInfo * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // coordinates
  if (!rosidl_runtime_c__double__Sequence__are_equal(
      &(lhs->coordinates), &(rhs->coordinates)))
  {
    return false;
  }
  // photo_num
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->photo_num), &(rhs->photo_num)))
  {
    return false;
  }
  return true;
}

bool
mirela_interfaces__msg__PhotoInfo__copy(
  const mirela_interfaces__msg__PhotoInfo * input,
  mirela_interfaces__msg__PhotoInfo * output)
{
  if (!input || !output) {
    return false;
  }
  // coordinates
  if (!rosidl_runtime_c__double__Sequence__copy(
      &(input->coordinates), &(output->coordinates)))
  {
    return false;
  }
  // photo_num
  if (!rosidl_runtime_c__String__copy(
      &(input->photo_num), &(output->photo_num)))
  {
    return false;
  }
  return true;
}

mirela_interfaces__msg__PhotoInfo *
mirela_interfaces__msg__PhotoInfo__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__PhotoInfo * msg = (mirela_interfaces__msg__PhotoInfo *)allocator.allocate(sizeof(mirela_interfaces__msg__PhotoInfo), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(mirela_interfaces__msg__PhotoInfo));
  bool success = mirela_interfaces__msg__PhotoInfo__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
mirela_interfaces__msg__PhotoInfo__destroy(mirela_interfaces__msg__PhotoInfo * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    mirela_interfaces__msg__PhotoInfo__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
mirela_interfaces__msg__PhotoInfo__Sequence__init(mirela_interfaces__msg__PhotoInfo__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__PhotoInfo * data = NULL;

  if (size) {
    data = (mirela_interfaces__msg__PhotoInfo *)allocator.zero_allocate(size, sizeof(mirela_interfaces__msg__PhotoInfo), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = mirela_interfaces__msg__PhotoInfo__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        mirela_interfaces__msg__PhotoInfo__fini(&data[i - 1]);
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
mirela_interfaces__msg__PhotoInfo__Sequence__fini(mirela_interfaces__msg__PhotoInfo__Sequence * array)
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
      mirela_interfaces__msg__PhotoInfo__fini(&array->data[i]);
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

mirela_interfaces__msg__PhotoInfo__Sequence *
mirela_interfaces__msg__PhotoInfo__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__PhotoInfo__Sequence * array = (mirela_interfaces__msg__PhotoInfo__Sequence *)allocator.allocate(sizeof(mirela_interfaces__msg__PhotoInfo__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = mirela_interfaces__msg__PhotoInfo__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
mirela_interfaces__msg__PhotoInfo__Sequence__destroy(mirela_interfaces__msg__PhotoInfo__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    mirela_interfaces__msg__PhotoInfo__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
mirela_interfaces__msg__PhotoInfo__Sequence__are_equal(const mirela_interfaces__msg__PhotoInfo__Sequence * lhs, const mirela_interfaces__msg__PhotoInfo__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!mirela_interfaces__msg__PhotoInfo__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
mirela_interfaces__msg__PhotoInfo__Sequence__copy(
  const mirela_interfaces__msg__PhotoInfo__Sequence * input,
  mirela_interfaces__msg__PhotoInfo__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(mirela_interfaces__msg__PhotoInfo);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    mirela_interfaces__msg__PhotoInfo * data =
      (mirela_interfaces__msg__PhotoInfo *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!mirela_interfaces__msg__PhotoInfo__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          mirela_interfaces__msg__PhotoInfo__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!mirela_interfaces__msg__PhotoInfo__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
