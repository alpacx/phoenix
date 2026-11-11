#pragma once
#include "cJSON.h"
#include <stdint.h>
void ph_history_init(void);
void ph_history_add(const char *country, const char *server, uint32_t id);
cJSON *ph_history_page(uint32_t before);
