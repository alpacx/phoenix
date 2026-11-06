#include "policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    uint32_t ip, mask;
    char out[24];
    assert(ph_cidr_parse("192.168.9.234/24", &ip, &mask) && ip == 0xc0a80900 && mask == 0xffffff00);
    ph_cidr_format(ip, mask, out, sizeof out);
    assert(!strcmp(out, "192.168.9.0/24"));
    assert(ph_cidr_parse("0.0.0.0/0", &ip, &mask) && !ip && !mask);
    const char *bad[] = {"",         "1.2.3",      "256.1.2.3",  "01.2.3.4", "1.2.3.4/33",
                         "1.2.3.4/", "1.2.3.4//1", "1.2.3.4/1x", "1.2.3.4.5"};
    for (size_t i = 0; i < sizeof bad / sizeof *bad; i++)
        assert(!ph_cidr_parse(bad[i], &ip, &mask));
    ph_policy p = {.schema = 1, .default_allow = false, .rule_count = 1, .forward_count = 1};
    p.rules[0] = (ph_named_rule){.name = "DNS",
                                 .enabled = true,
                                 .match = {.ingress = PH_AP,
                                           .direction = PH_FORWARD,
                                           .protocol = 17,
                                           .port_first = 53,
                                           .port_last = 53,
                                           .allow = true}};
    p.forwards[0] = (ph_port_forward){.name = "Service",
                                      .enabled = true,
                                      .vpn = true,
                                      .protocol = 6,
                                      .external_port = 8080,
                                      .internal_port = 80,
                                      .target = 0xc0a80902,
                                      .source = 0xc0a80000,
                                      .source_mask = 0xffff0000};
    assert(ph_policy_valid(&p));
    assert(ph_forward_source_allowed(&p.forwards[0], 0xc0a80801));
    assert(!ph_forward_source_allowed(&p.forwards[0], 0x08080808));
    ph_firewall f = {.allowed = 14, .blocked = 2};
    ph_policy_compile(&p, &f);
    assert(f.rule_count == 5 && f.allowed == 14 && f.blocked == 2);
    assert(f.rules[0].direction == PH_LOCAL && f.rules[1].ingress == PH_AP &&
           f.rules[2].port_first == 53 && !f.rules[4].allow);
    p.rules[0].match.direction = PH_LOCAL;
    assert(!ph_policy_valid(&p));
    p.rules[0].match.direction = PH_FORWARD;
    p.rules[0].match.src_mask = 0xff00ff00;
    assert(!ph_policy_valid(&p));
    p.rules[0].match.src_mask = 0;
    for (unsigned i = 0; i < 65536; i++) {
        p.forwards[0].external_port = i;
        bool valid = i && i != 80 && i != 51820 && !(i >= 49152 && i <= 61439);
        assert(ph_policy_valid(&p) == valid);
    }
    p.forwards[0].external_port = 8080;
    p.forward_count = 2;
    p.forwards[1] = p.forwards[0];
    assert(!ph_policy_valid(&p));
    p.forwards[1].external_port = 8081;
    assert(!ph_policy_valid(&p));
    p.forwards[1].internal_port = 81;
    assert(ph_policy_valid(&p));
    p.forwards[1].target = 0x08080808;
    assert(!ph_policy_valid(&p));
    puts("Policy: canonical CIDR, mandatory admin rules, reserved ports, source restrictions and "
         "duplicate NAT mappings PASS");
}
