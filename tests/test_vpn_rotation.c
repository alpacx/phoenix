#include "vpn_rotation.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    assert(ph_vpn_next_country(0, 0, 0) == SIZE_MAX);
    assert(ph_vpn_next_country(1, 0, UINT32_MAX) == 0);
    assert(ph_vpn_next_country(150, SIZE_MAX, UINT32_MAX) == 149);
    ph_vpn_location s[] = {{1, "IT"}, {2, "IT"}, {3, "DE"}, {4, "US"}};
    for (uint32_t i = 0; i < 100000; i++) {
        uint32_t r = i * 2654435761U;
        for (size_t previous = 0; previous < 150; previous++) {
            size_t next = ph_vpn_next_country(150, previous, r);
            assert(next < 150 && next != previous);
        }
        assert(ph_vpn_pick(s, 4, "IT", 1, r, r) == 2);
        assert(ph_vpn_pick(s, 4, "DE", 3, r, r) == 3);
        assert(ph_vpn_pick(s, 4, "FR", 1, r, r) == UINT32_MAX);
        uint32_t id = ph_vpn_pick(s, 4, "", 1, r, r);
        assert(id >= 2 && id <= 4);
    }
    assert(ph_vpn_pick(s, 4, "", UINT32_MAX, 0, 0) == 1);
    assert(ph_vpn_pick(s, 4, "", UINT32_MAX, UINT32_MAX, 0) == 4);
    assert(ph_vpn_pick(s, 0, "", 1, 0, 0) == UINT32_MAX);
    assert(ph_vpn_pick(s, 4, "Italy", 1, 0, 0) == UINT32_MAX);
    assert(ph_vpn_pick(NULL, 4, "", 1, 0, 0) == UINT32_MAX);
    assert(!ph_vpn_country_valid("I", false));
    puts("VPN rotation: fixed-country isolation, random selection and empty pools passed");
}
