#include "policy.h"
#include <stdio.h>
#include <string.h>
static bool mask_valid(uint32_t m) {
    uint32_t inv = ~m;
    return (inv & (inv + 1)) == 0;
}
static bool label(const char *s) {
    size_t n = 0;
    while (n < PH_LABEL_SIZE && s[n]) {
        if ((unsigned char)s[n] < 32)
            return false;
        n++;
    }
    return n > 0 && n < PH_LABEL_SIZE;
}
bool ph_cidr_parse(const char *s, uint32_t *address, uint32_t *mask) {
    if (!s || !*s)
        return false;
    uint32_t ip = 0;
    for (unsigned i = 0; i < 4; i++) {
        unsigned value = 0, digits = 0;
        const char *start = s;
        while (*s >= '0' && *s <= '9') {
            value = value * 10 + (*s++ - '0');
            if (++digits > 3 || value > 255)
                return false;
        }
        if (!digits || (digits > 1 && *start == '0'))
            return false;
        ip = (ip << 8) | value;
        if (i < 3 && *s++ != '.')
            return false;
    }
    unsigned prefix = 32;
    if (*s == '/') {
        s++;
        if (!*s)
            return false;
        prefix = 0;
        unsigned digits = 0;
        while (*s >= '0' && *s <= '9') {
            prefix = prefix * 10 + (*s++ - '0');
            if (++digits > 2 || prefix > 32)
                return false;
        }
    }
    if (*s)
        return false;
    *mask = prefix ? 0xffffffffU << (32 - prefix) : 0;
    *address = ip & *mask;
    return true;
}
void ph_cidr_format(uint32_t a, uint32_t m, char *out, size_t size) {
    unsigned prefix = 0;
    for (uint32_t bit = 0x80000000; bit && (m & bit); bit >>= 1)
        prefix++;
    snprintf(out, size, "%u.%u.%u.%u/%u", (unsigned)(a >> 24), (unsigned)((a >> 16) & 255),
             (unsigned)((a >> 8) & 255), (unsigned)(a & 255), prefix);
}
bool ph_policy_valid(const ph_policy *p) {
    if (!p || p->schema != 1 || p->rule_count > PH_POLICY_RULES ||
        p->forward_count > PH_PORT_FORWARDS)
        return false;
    for (size_t i = 0; i < p->rule_count; i++) {
        const ph_named_rule *n = &p->rules[i];
        const ph_rule *r = &n->match;
        if (!label(n->name) || (r->ingress != PH_AP && r->ingress != PH_USB) ||
            r->direction != PH_FORWARD ||
            (r->protocol != 0 && r->protocol != 1 && r->protocol != 6 && r->protocol != 17) ||
            !mask_valid(r->src_mask) || !mask_valid(r->dst_mask) || (r->src & ~r->src_mask) ||
            (r->dst & ~r->dst_mask) || r->port_last < r->port_first ||
            (!r->port_first && r->port_last) ||
            ((r->port_first || r->port_last) && r->protocol != 6 && r->protocol != 17))
            return false;
    }
    for (size_t i = 0; i < p->forward_count; i++) {
        const ph_port_forward *f = &p->forwards[i];
        uint32_t network = f->target & 0xffffff00;
        if (!label(f->name) || (f->protocol != 6 && f->protocol != 17) || !f->external_port ||
            !f->internal_port || (network != 0xc0a80700 && network != 0xc0a80900) ||
            (f->target & 255) < 2 || (f->target & 255) == 255 || !mask_valid(f->source_mask) ||
            (f->source & ~f->source_mask) || f->external_port == 80 || f->external_port == 51820 ||
            (f->external_port >= 49152 && f->external_port <= 61439))
            return false;
        for (size_t j = 0; j < i; j++) {
            const ph_port_forward *b = &p->forwards[j];
            if (f->enabled && b->enabled && f->vpn == b->vpn && f->protocol == b->protocol &&
                (f->external_port == b->external_port ||
                 (f->target == b->target && f->internal_port == b->internal_port)))
                return false;
        }
    }
    return true;
}
void ph_policy_compile(const ph_policy *p, ph_firewall *fw) {
    fw->rule_count = 0;
    for (unsigned i = 0; i < 2; i++)
        fw->rules[fw->rule_count++] = (ph_rule){.ingress = i ? PH_AP : PH_USB,
                                                .direction = PH_LOCAL,
                                                .protocol = 6,
                                                .port_first = 80,
                                                .port_last = 80,
                                                .allow = true};
    for (size_t i = 0; i < p->rule_count; i++)
        if (p->rules[i].enabled)
            fw->rules[fw->rule_count++] = p->rules[i].match;
    for (unsigned i = 0; i < 2; i++)
        fw->rules[fw->rule_count++] = (ph_rule){
            .ingress = i ? PH_AP : PH_USB, .direction = PH_FORWARD, .allow = p->default_allow};
}
bool ph_forward_source_allowed(const ph_port_forward *p, uint32_t src) {
    return (src & p->source_mask) == p->source;
}
