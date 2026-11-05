#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
 char private_key[45],public_key[45],psk[45],address[16],endpoint[16],dns[16];
 uint16_t port,keepalive,mtu;
} ph_wg_profile;
/* Strict one-peer IPv4 full-tunnel subset, no scripts, hostnames or silent partial imports. */
bool ph_wg_parse(const char *text,size_t len,ph_wg_profile *out);
