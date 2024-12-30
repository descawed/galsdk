#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <galerians/types.h>
#include <galerians/globals.h>
#include <galerians/api.h>

#define MODULE_ID(n) uint32_t module_id __attribute__ ((section ("MODULE_ID"))) = n

#ifdef __cplusplus
}
#endif