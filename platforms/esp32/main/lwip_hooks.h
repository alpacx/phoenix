#pragma once
struct pbuf;
struct netif;
int ph_ip4_input(struct pbuf *p, struct netif *n);
#define LWIP_HOOK_IP4_INPUT(p, n) ph_ip4_input(p, n)

#include "lwip/ip4_addr.h"
struct netif *ph_route(const ip4_addr_t *src, const ip4_addr_t *dst);
int ph_canforward(struct pbuf *p, unsigned long address);
#undef LWIP_HOOK_IP4_ROUTE_SRC
#define LWIP_HOOK_IP4_ROUTE_SRC(src, dst) ph_route(src, dst)
#define LWIP_HOOK_IP4_CANFORWARD(p, addr) ph_canforward(p, addr)
