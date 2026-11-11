#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define PH_MAX_RULES 32
/* Host byte order addresses, no dynamic allocation, caller serializes access. */
typedef enum { PH_USB, PH_ETH, PH_WIFI, PH_AP, PH_WG } ph_iface;
typedef enum { PH_LOCAL, PH_FORWARD } ph_direction;
typedef struct {
    uint32_t src, dst;
    uint16_t sport, dport;
    uint8_t protocol, tcp_flags;
} ph_packet;
typedef struct {
    uint32_t src, src_mask, dst, dst_mask;
    uint16_t port_first, port_last;
    uint8_t protocol;
    ph_iface ingress;
    ph_direction direction;
    bool allow;
} ph_rule;
typedef struct {
    ph_rule rules[PH_MAX_RULES];
    size_t rule_count;
    bool direct_enabled, uplink_ready, tunnel_ready;
    uint64_t allowed, blocked, malformed;
} ph_firewall;
bool ph_parse_ipv4(const uint8_t *data, size_t size, ph_packet *packet);
bool ph_allow(ph_firewall *fw, const uint8_t *ip, size_t len, ph_iface in, ph_iface out,
              ph_direction direction);
bool ph_tcp_clamp_mss(uint8_t *ip, size_t len, uint16_t mtu);
