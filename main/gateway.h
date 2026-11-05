#pragma once
#include "esp_netif.h"
#include "phoenix.h"
extern esp_netif_t *ph_usb,*ph_eth;
void ph_gateway_start(void);
void ph_gateway_direct(bool enabled);
void ph_gateway_uplink(bool ready);
void ph_gateway_snapshot(ph_firewall *out);

void ph_gateway_guard_eth(void);
