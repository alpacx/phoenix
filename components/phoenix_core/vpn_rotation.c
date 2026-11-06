#include "vpn_rotation.h"
#include <string.h>
bool ph_vpn_country_valid(const char *c, bool empty_allowed) {
    if (!c)
        return false;
    if (!*c)
        return empty_allowed;
    return c[0] >= 'A' && c[0] <= 'Z' && c[1] >= 'A' && c[1] <= 'Z' && c[2] == 0;
}
uint32_t ph_vpn_pick(const ph_vpn_location *s, size_t n, const char *country, uint32_t current,
                     uint32_t cr, uint32_t sr) {
    if (!s || n > PH_VPN_SERVERS || !ph_vpn_country_valid(country, true))
        return UINT32_MAX;
    char countries[PH_VPN_SERVERS][3];
    size_t nc = 0;
    bool alternative = false;
    for (size_t i = 0; i < n; i++) {
        if (!ph_vpn_country_valid(s[i].country, false) || s[i].id == UINT32_MAX)
            continue;
        if (*country && strcmp(country, s[i].country))
            continue;
        if (s[i].id != current)
            alternative = true;
    }
    for (size_t i = 0; i < n; i++) {
        if (!ph_vpn_country_valid(s[i].country, false) || s[i].id == UINT32_MAX)
            continue;
        if ((*country && strcmp(country, s[i].country)) || (alternative && s[i].id == current))
            continue;
        size_t j = 0;
        for (; j < nc; j++)
            if (!strcmp(countries[j], s[i].country))
                break;
        if (j == nc)
            memcpy(countries[nc++], s[i].country, 3);
    }
    if (!nc)
        return UINT32_MAX;
    const char *chosen = countries[((uint64_t)cr * nc) >> 32];
    size_t eligible[PH_VPN_SERVERS], ne = 0;
    for (size_t i = 0; i < n; i++)
        if (s[i].id != UINT32_MAX && !strcmp(chosen, s[i].country) &&
            (!alternative || s[i].id != current))
            eligible[ne++] = i;
    return s[eligible[((uint64_t)sr * ne) >> 32]].id;
}

size_t ph_vpn_next_country(size_t count, size_t previous, uint32_t random) {
    if (!count)
        return SIZE_MAX;
    bool exclude = count > 1 && previous < count;
    size_t index = ((uint64_t)random * (count - exclude)) >> 32;
    return exclude && index >= previous ? index + 1 : index;
}

bool ph_vpn_country_restricted(const char *country) {
    static const char codes[][3] = {"CN", "RU", "BY", "TR", "IQ", "AE", "OM", "IN",
                                    "IR", "EG", "TM", "KP", "UG", "MM", "SA", "VE"};
    if (!ph_vpn_country_valid(country, false))
        return false;
    for (size_t i = 0; i < sizeof codes / sizeof *codes; i++)
        if (!strcmp(country, codes[i]))
            return true;
    return false;
}
