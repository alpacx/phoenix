#include "wg_profile.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
/* Public synthetic parser fixture; never used as credentials or endpoint. */
static const char *config =
    "[Interface]\nPrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\nAddress = "
    "10.9.0.2/32\nDNS = 10.9.0.1\nMTU = 1380\n[Peer]\nPublicKey = "
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=\nAllowedIPs = 0.0.0.0/0\nEndpoint = "
    "192.0.2.1:51820\nPersistentKeepalive = 25\n";
int main(void) {
    ph_wg_profile p;
    assert(ph_wg_parse(config, strlen(config), &p));
    assert(p.port == 51820 && p.keepalive == 25 && p.mtu == 1380);
    assert(!strcmp(p.address, "10.9.0.2") && p.prefix == 32);
    char buf[4096];
    strcpy(buf, config);
    memcpy(strstr(buf, "/32"), "/24", 3);
    assert(ph_wg_parse(buf, strlen(buf), &p) && p.prefix == 24);
    const char *bad[] = {"PostUp = echo danger\n", "AllowedIPs = 10.0.0.0/8\n",
                         "Endpoint = example.org:51820\n", "[Peer]\n",
                         "PersistentKeepalive = 65536\n"};
    for (size_t i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        snprintf(buf, sizeof buf, "%s%s", config, bad[i]);
        assert(!ph_wg_parse(buf, strlen(buf), &p));
    }
    assert(!ph_wg_parse("", 0, &p));
    assert(!ph_wg_parse(config, 5000, &p));
    strcpy(buf, config);
    buf[20] = 0;
    assert(!ph_wg_parse(buf, strlen(config), &p));
    strcpy(buf, config);
    char *end = strstr(buf, "192.0.2.1");
    memcpy(end, "999.0.2.1", 9);
    assert(!ph_wg_parse(buf, strlen(buf), &p));
    uint32_t x = 9;
    for (unsigned i = 0; i < 20000; i++) {
        for (unsigned j = 0; j < sizeof buf; j++) {
            x = x * 1664525 + 1013904223;
            buf[j] = x >> 24;
        }
        ph_wg_parse(buf, i % sizeof buf, &p);
    }
    puts("WireGuard parser: valid subset, duplicate fields, overflow, script/hostname rejection + "
         "20000 malformed profiles PASS");
}
