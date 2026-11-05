#include "phoenix.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void checksum(uint8_t *p) {
    p[10] = p[11] = 0;
    unsigned s = 0;
    for (int i = 0; i < 20; i += 2)
        s += (p[i] << 8) | p[i + 1];
    while (s >> 16)
        s = (s & 65535) + (s >> 16);
    s = ~s;
    p[10] = s >> 8;
    p[11] = s;
}
int main(void) {
    uint8_t p[44] = {0x45, 0, 0, 28, 0, 0, 0x40, 0,    64, 17, 0, 0, 192, 168,
                     7,    2, 1, 1,  1, 1, 0xab, 0xcd, 0,  53, 0, 8, 0,   0};
    checksum(p);
    ph_packet pkt;
    assert(ph_parse_ipv4(p, 28, &pkt));
    assert(pkt.src == 0xc0a80702 && pkt.dport == 53);
    ph_firewall f = {.uplink_ready = true,
                     .rule_count = 1,
                     .rules = {{.ingress = PH_USB, .direction = PH_FORWARD, .allow = true}}};
    assert(!ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    f.tunnel_ready = true;
    assert(!ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    assert(ph_allow(&f, p, 28, PH_USB, PH_WG, PH_FORWARD));
    f.tunnel_ready = false;
    assert(!ph_allow(&f, p, 28, PH_USB, PH_WG, PH_FORWARD));
    f.direct_enabled = true;
    assert(ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    f.uplink_ready = false;
    assert(!ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    f.uplink_ready = true;
    assert(!ph_allow(&f, p, 28, PH_ETH, PH_USB, PH_FORWARD));
    assert(!ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_LOCAL));
    f.rules[0].port_first = 443;
    f.rules[0].port_last = 443;
    assert(!ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    f.rules[0].port_first = 53;
    f.rules[0].port_last = 53;
    assert(ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    f.rules[0].src = 0x0a000000;
    f.rules[0].src_mask = 0xff000000;
    assert(!ph_allow(&f, p, 28, PH_USB, PH_ETH, PH_FORWARD));
    for (size_t i = 0; i < 28; i++)
        assert(!ph_parse_ipv4(p, i, &pkt));
    p[6] = 0x20;
    checksum(p);
    assert(!ph_parse_ipv4(p, 28, &pkt));
    p[6] = 0x40;
    checksum(p);
    p[0] = 0x60;
    assert(!ph_parse_ipv4(p, 28, &pkt));
    p[0] = 0x45;
    p[25] = 7;
    assert(!ph_parse_ipv4(p, 28, &pkt));
    p[25] = 8;
    p[10] ^= 1;
    assert(!ph_parse_ipv4(p, 28, &pkt));
    checksum(p);
    p[9] = 6;
    p[3] = 44;
    p[32] = 0x60;
    p[33] = 2;
    p[40] = 2;
    p[41] = 4;
    p[42] = 5;
    p[43] = 0xb4;
    checksum(p);
    assert(ph_tcp_clamp_mss(p, 44, 1380));
    assert(p[42] == 5 && p[43] == 0x3c);
    p[41] = 3;
    assert(!ph_tcp_clamp_mss(p, 44, 1380));
    /* Deterministic malformed packet corpus exercises every bounded read under ASan/UBSan. */
    uint32_t x = 7;
    uint8_t fuzz[1600];
    for (unsigned i = 0; i < 100000; i++) {
        for (size_t j = 0; j < sizeof fuzz; j++) {
            x = x * 1664525 + 1013904223;
            fuzz[j] = x >> 24;
        }
        ph_parse_ipv4(fuzz, i % sizeof fuzz, &pkt);
    }
    puts("firewall: gate, direction, ports, CIDR, truncation, fragments, IPv6, checksum + 100000 "
         "malformed packets PASS");
}
