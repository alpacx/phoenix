#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define PH_VPN_SERVERS 64
/* ISO 3166-1 alpha-2 country codes; empty selection means all countries. */
typedef struct {
    uint32_t id;
    char country[3];
} ph_vpn_location;
/* Country is chosen uniformly, then a server in that country. The current server
 * is excluded whenever an alternative exists. A fixed country NEVER falls back
 * to another country. UINT32_MAX means no eligible server. */
uint32_t ph_vpn_pick(const ph_vpn_location *servers, size_t count, const char *country,
                     uint32_t current, uint32_t country_random, uint32_t server_random);
bool ph_vpn_country_valid(const char *country, bool empty_allowed);

/* Uniform index excluding previous when alternatives exist. */
size_t ph_vpn_next_country(size_t count, size_t previous, uint32_t random);

/* Phoenix exclusion preset based on NordVPN restrictions article, 2026-11-06.
 * This is not a provider rating of server security. */
bool ph_vpn_country_restricted(const char *country);
