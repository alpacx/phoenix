#pragma once
#include "lwip/netif.h"
#include "wg_profile.h"
extern struct netif *ph_wg;
/* Caller holds lwIP core lock for every function. */
bool ph_vpn_start(const ph_wg_profile *profile);
void ph_vpn_stop(void);
bool ph_vpn_up(void);
bool ph_vpn_outer(uint32_t src, uint16_t sport, uint16_t dport);

bool ph_vpn_outer_tx(uint32_t dst, uint16_t sport, uint16_t dport);
