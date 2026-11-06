#include "vpn.h"
#include "esp_netif.h"
#include "esp_netif_net_stack.h"
#include "gateway.h"
#include "lwip/ip.h"
#include "mbedtls/base64.h"
#include "wireguard-platform.h"
#include "wireguardif.h"
#include <string.h>
#include <time.h>
static struct netif wg;
struct netif *ph_wg;
static uint8_t peer_id;
static uint32_t endpoint;
static uint16_t endpoint_port;
static bool platform_ready;
bool ph_vpn_up(void) {
    return ph_wg && wireguardif_peer_is_up(ph_wg, peer_id, NULL, NULL) == ERR_OK;
}
bool ph_vpn_outer_tx(uint32_t dst, uint16_t sport, uint16_t dport) {
    return ph_wg && dst == endpoint && sport == 51820 && dport == endpoint_port;
}
bool ph_vpn_outer(uint32_t src, uint16_t sport, uint16_t dport) {
    return ph_wg && src == endpoint && sport == endpoint_port && dport == 51820;
}
void ph_vpn_stop(void) {
    if (!ph_wg)
        return;
    wireguardif_disconnect(ph_wg, peer_id);
    wireguardif_remove_peer(ph_wg, peer_id);
    wireguardif_shutdown(ph_wg);
    netif_remove(ph_wg);
    wireguardif_fini(ph_wg);
    ph_wg = NULL;
    ph_gateway_refresh_maps();
    memset(&wg, 0, sizeof wg);
}
bool ph_vpn_start(const ph_wg_profile *p) {
    ph_vpn_stop();
    if (!ph_selected || time(NULL) < 1700000000)
        return false; /* sane clock required to avoid stale handshake timestamps */
    if (!platform_ready) {
        esp_err_t e = wireguard_platform_init();
        if (e != ESP_OK)
            return false;
        platform_ready = true;
    }
    ip4_addr_t addr, mask, gw;
    ip4addr_aton(p->address, &addr);
    ip4_addr_set_u32(&mask, lwip_htonl(0xffffffffU << (32 - p->prefix)));
    ip4_addr_set_zero(&gw);
    struct wireguardif_init_data init = {.private_key = p->private_key,
                                         .listen_port = 51820,
                                         .bind_netif = esp_netif_get_netif_impl(ph_selected)};
    if (!netif_add(&wg, &addr, &mask, &gw, &init, wireguardif_init, ip_input))
        return false;
    ph_wg = &wg;
    wg.mtu = p->mtu;
    netif_set_up(&wg);
    struct wireguardif_peer peer;
    wireguardif_peer_init(&peer);
    peer.public_key = p->public_key;
    ip_addr_set_zero(&peer.allowed_ip);
    ip_addr_set_zero(&peer.allowed_mask);
    ipaddr_aton(p->endpoint, &peer.endpoint_ip);
    peer.endport_port = p->port;
    peer.keep_alive = p->keepalive;
    uint8_t psk[32];
    size_t olen = 0;
    if (p->psk[0]) {
        if (mbedtls_base64_decode(psk, sizeof psk, &olen, (const unsigned char *)p->psk, 44) ||
            olen != 32)
            goto fail;
        peer.preshared_key = psk;
    }
    if (wireguardif_add_peer(&wg, &peer, &peer_id) != ERR_OK)
        goto fail;
    endpoint = lwip_ntohl(ip4_addr_get_u32(ip_2_ip4(&peer.endpoint_ip)));
    endpoint_port = p->port;
    memset(psk, 0, sizeof psk);
    if (wireguardif_connect(&wg, peer_id) == ERR_OK) {
        ph_gateway_refresh_maps();
        return true;
    }
fail:
    memset(psk, 0, sizeof psk);
    ph_vpn_stop();
    return false;
}
