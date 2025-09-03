// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from mirela_interfaces:msg/LineInfo.idl
// generated code does not contain a copyright notice
#include "mirela_interfaces/msg/detail/line_info__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


bool
mirela_interfaces__msg__LineInfo__init(mirela_interfaces__msg__LineInfo * msg)
{
  if (!msg) {
    return false;
  }
  // center_x
  // center_y
  // angle
  // width
  // height
  return true;
}

void
mirela_interfaces__msg__LineInfo__fini(mirela_interfaces__msg__LineInfo * msg)
{
  if (!msg) {
    return;
  }
  // center_x
  // center_y
  // angle
  // width
  // height
}

bool
mirela_interfaces__msg__LineInfo__are_equal(const mirela_interfaces__msg__LineInfo * lhs, const mirela_interfaces__msg__LineInfo * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // center_x
  if (lhs->center_x != rhs->center_x) {
    return false;
  }
  // center_y
  if (lhs->center_y != rhs->center_y) {
    return false;
  }
  // angle
  if (lhs->angle != rhs->angle) {
    return false;
  }
  // width
  if (lhs->width != rhs->width) {
    return false;
  }
  // height
  if (lhs->height != rhs->height) {
    return false;
  }
  return true;
}

bool
mirela_interfaces__msg__LineInfo__copy(
  const mirela_interfaces__msg__LineInfo * input,
  mirela_interfaces__msg__LineInfo * output)
{
  if (!input || !output) {
    return false;
  }
  // center_x
  output->center_x = input->center_x;
  // center_y
  output->center_y = input->center_y;
  // angle
  output->angle = input->angle;
  // width
  output->width = input->width;
  // height
  output->height = input->height;
  return true;
}

mirela_interfaces__msg__LineInfo *
mirela_interfaces__msg__LineInfo__create()
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__LineInfo * msg = (mirela_interfaces__msg__LineInfo *)allocator.allocate(sizeof(mirela_interfaces__msg__LineInfo), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(mirela_interfaces__msg__LineInfo));
  bool success = mirela_interfaces__msg__LineInfo__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
mirela_interfaces__msg__LineInfo__destroy(mirela_interfaces__msg__LineInfo * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    mirela_interfaces__msg__LineInfo__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
mirela_interfaces__msg__LineInfo__Sequence__init(mirela_interfaces__msg__LineInfo__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__LineInfo * data = NULL;

  if (size) {
    data = (mirela_interfaces__msg__LineInfo *)allocator.zero_allocate(size, sizeof(mirela_interfaces__msg__LineInfo), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = mirela_interfaces__msg__LineInfo__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        mirela_interfaces__msg__LineInfo__fini(&data[i - 1]);
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
mirela_interfaces__msg__LineInfo__Sequence__fini(mirela_interfaces__msg__LineInfo__Sequence * array)
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
      mirela_interfaces__msg__LineInfo__fini(&array->data[i]);
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

mirela_interfaces__msg__LineInfo__Sequence *
mirela_interfaces__msg__LineInfo__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  mirela_interfaces__msg__LineInfo__Sequence * array = (mirela_interfaces__msg__LineInfo__Sequence *)allocator.allocate(sizeof(mirela_interfaces__msg__LineInfo__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = mirela_interfaces__msg__LineInfo__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
mirela_interfaces__msg__LineInfo__Sequence__destroy(mirela_interfaces__msg__LineInfo__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    mirela_interfaces__msg__LineInfo__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
mirela_interfaces__msg__LineInfo__Sequence__are_equal(const mirela_interfaces__msg__LineInfo__Sequence * lhs, const mirela_interfaces__msg__LineInfo__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!mirela_interfaces__msg__LineInfo__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
mirela_interfaces__msg__LineInfo__Sequence__copy(
  const mirela_interfaces__msg__LineInfo__Sequence * input,
  mirela_interfaces__msg__LineInfo__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    const size_t allocation_size =
      input->size * sizeof(mirela_interfaces__msg__LineInfo);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    mirela_interfaces__msg__LineInfo * data =
      (mirela_interfaces__msg__LineInfo *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!mirela_interfaces__msg__LineInfo__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          mirela_interfaces__msg__LineInfo__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!mirela_interfaces__msg__LineInfo__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
