#pragma once
#include "phoenix.h"
#define PH_POLICY_RULES 20
#define PH_PORT_FORWARDS 8
#define PH_LABEL_SIZE 33
typedef struct {
    char name[PH_LABEL_SIZE];
    bool enabled;
    ph_rule match;
} ph_named_rule;
typedef struct {
    char name[PH_LABEL_SIZE];
    bool enabled, vpn;
    uint8_t protocol;
    uint16_t external_port, internal_port;
    uint32_t target, source, source_mask;
} ph_port_forward;
typedef struct {
    uint32_t schema, revision;
    bool default_allow;
    size_t rule_count, forward_count;
    ph_named_rule rules[PH_POLICY_RULES];
    ph_port_forward forwards[PH_PORT_FORWARDS];
} ph_policy;
bool ph_cidr_parse(const char *text, uint32_t *address, uint32_t *mask);
void ph_cidr_format(uint32_t address, uint32_t mask, char *out, size_t size);
bool ph_policy_valid(const ph_policy *p);
void ph_policy_compile(const ph_policy *p, ph_firewall *fw);
bool ph_forward_source_allowed(const ph_port_forward *p, uint32_t source);
