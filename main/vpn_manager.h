#pragma once
#include "cJSON.h"
#include "esp_err.h"
#include "wg_profile.h"
void ph_vpn_manager_init(void);
bool ph_vpn_manager_configured(void);
void ph_vpn_manager_bench(const ph_wg_profile *profile);
/* Queued commands: configure WireGuard/Nord, connect, disconnect, rotate, direct,
 * forget, catalog_test. Token is ephemeral; only derived WG key is persisted. */
esp_err_t ph_vpn_manager_command(const cJSON *command);
cJSON *ph_vpn_manager_status(void);
