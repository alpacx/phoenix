#include "gateway.h"
#include "dhcpserver/dhcpserver.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif_net_stack.h"
#include "lwip/etharp.h"
#include "lwip/ip.h"
#include "lwip/ip4_addr.h"
#include "lwip/lwip_napt.h"
#include "lwip/netif.h"
#include "lwip/pbuf.h"
#include "lwip/tcpip.h"
#include "sdkconfig.h"
#include "tinyusb.h"
#include "tinyusb_default_config.h"
#include "tinyusb_net.h"
#include "vpn.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef CONFIG_PHOENIX_USB_LAB
#define CONFIG_PHOENIX_USB_LAB 0
#endif
esp_netif_t *ph_usb, *ph_eth, *ph_sta, *ph_ap, *ph_selected;
static ph_firewall fw;
static uint8_t scratch[1514]; /* only accessed under lwIP core lock */
void ph_gateway_snapshot(ph_firewall *out) {
    LOCK_TCPIP_CORE();
    fw.tunnel_ready = ph_vpn_up();
    *out = fw;
    UNLOCK_TCPIP_CORE();
}
void ph_gateway_network_status(ph_network_status *out) {
    memset(out, 0, sizeof *out);
    LOCK_TCPIP_CORE();
    esp_netif_t *interfaces[] = {ph_eth, ph_sta, ph_ap};
    bool link[3] = {0}, ip[3] = {0};
    for (unsigned i = 0; i < 3; i++) {
        if (!interfaces[i])
            continue;
        struct netif *n = esp_netif_get_netif_impl(interfaces[i]);
        link[i] = netif_is_up(n) && netif_is_link_up(n);
        ip[i] = link[i] && !ip4_addr_isany_val(*netif_ip4_addr(n));
    }
    out->ethernet_link = link[0];
    out->ethernet_ip = ip[0];
    out->wifi_link = link[1];
    out->wifi_ip = ip[1];
    out->ap_active = ip[2];
    out->selected_wifi = ph_selected && ph_selected == ph_sta;
    UNLOCK_TCPIP_CORE();
    if (ph_usb) {
        out->usb_mounted = tud_mounted();
        out->usb_suspended = tud_suspended();
    }
}
static bool same(struct netif *n, esp_netif_t *e) {
    return e && n == esp_netif_get_netif_impl(e);
}
static bool client_addr(uint32_t addr) {
    return (addr & 0xffffff00) == 0xc0a80700 || (addr & 0xffffff00) == 0xc0a80800;
}
static void flush_nat(void) {
    esp_netif_t *uplinks[] = {ph_eth, ph_sta};
    for (unsigned i = 0; i < 2; i++)
        if (uplinks[i])
            etharp_cleanup_netif(esp_netif_get_netif_impl(uplinks[i]));
    esp_netif_t *clients[] = {ph_usb, ph_ap};
    for (unsigned i = 0; i < 2; i++)
        if (clients[i]) {
            struct netif *n = esp_netif_get_netif_impl(clients[i]);
            if (n->napt)
                ip_napt_enable_no(n->num, 0);
        }
    for (unsigned i = 0; i < 2; i++)
        if (clients[i]) {
            struct netif *n = esp_netif_get_netif_impl(clients[i]);
            if (netif_is_up(n))
                ip_napt_enable_no(n->num, 1);
        }
}
void ph_gateway_direct(bool enabled) {
    LOCK_TCPIP_CORE();
    fw.direct_enabled = false;
    ph_vpn_stop();
    flush_nat();
    fw.direct_enabled = enabled;
    UNLOCK_TCPIP_CORE();
}
void ph_gateway_network_event(esp_netif_t *net, bool ready) {
    LOCK_TCPIP_CORE();
    if (net == ph_selected) {
        fw.uplink_ready = ready;
        if (!ready) {
            ph_vpn_stop();
            flush_nat();
        }
    }
    UNLOCK_TCPIP_CORE();
}
void ph_gateway_uplink(bool ready) {
    ph_gateway_network_event(ph_eth, ready);
}
esp_err_t ph_gateway_select(bool wifi) {
    esp_netif_t *selected = wifi ? ph_sta : ph_eth;
    if (!selected)
        return ESP_ERR_INVALID_STATE;
    LOCK_TCPIP_CORE();
    fw.direct_enabled = false;
    fw.uplink_ready = false;
    ph_vpn_stop();
    flush_nat();
    ph_selected = selected;
    struct netif *n = esp_netif_get_netif_impl(selected);
    uint32_t mask = lwip_ntohl(netif_ip4_netmask(n)->addr),
             ip = lwip_ntohl(netif_ip4_addr(n)->addr);
    fw.uplink_ready = netif_is_up(n) && netif_is_link_up(n) && ip &&
                      ((ip & mask) != (0xc0a80701 & mask)) && ((ip & mask) != (0xc0a80801 & mask));
    UNLOCK_TCPIP_CORE();
    return esp_netif_set_default_netif(selected);
}
/* Runs in tcpip thread before NAT/local delivery; an unrecognized interface fails closed. */
int ph_ip4_input(struct pbuf *p, struct netif *n) {
    ph_packet pkt;
    bool ok = false;
    if (p->tot_len > sizeof scratch)
        goto drop;
    pbuf_copy_partial(p, scratch, p->tot_len, 0);
    if (!ph_parse_ipv4(scratch, p->tot_len, &pkt)) {
        fw.malformed++;
        goto drop;
    }
    fw.tunnel_ready = ph_vpn_up();
    if (same(n, ph_usb) || same(n, ph_ap)) {
        bool usb = same(n, ph_usb);
        uint32_t network = usb ? 0xc0a80700 : 0xc0a80800;
        ph_iface ingress = usb ? PH_USB : PH_AP;
        bool dhcp = pkt.protocol == 17 && pkt.sport == 68 && pkt.dport == 67 &&
                    (pkt.dst == 0xffffffff || pkt.dst == network + 1);
        if (dhcp && (pkt.src == 0 || (pkt.src & 0xffffff00) == network))
            return 0;
        if ((pkt.src & 0xffffff00) != network || pkt.src == network || pkt.src == network + 1 ||
            pkt.src == network + 255)
            goto drop;
        if (pkt.dst == network + 1)
            ok = ph_allow(&fw, scratch, p->tot_len, ingress, ingress, PH_LOCAL);
        else {
            if (client_addr(pkt.dst))
                goto drop; /* no implicit USB/AP LAN exception */
            ok = ph_allow(&fw, scratch, p->tot_len, ingress,
                          fw.direct_enabled ? (ph_selected == ph_sta ? PH_WIFI : PH_ETH) : PH_WG,
                          PH_FORWARD);
        }
    } else if (same(n, ph_eth) || same(n, ph_sta)) {
        bool dhcp = pkt.protocol == 17 && pkt.sport == 67 && pkt.dport == 68;
        if (dhcp)
            return 0;
        if (!same(n, ph_selected) || pkt.dst != lwip_ntohl(netif_ip4_addr(n)->addr))
            goto drop;
        if (pkt.protocol == 17 && ph_vpn_outer(pkt.src, pkt.sport, pkt.dport))
            return 0;
        ok = fw.direct_enabled && fw.uplink_ready &&
             (((pkt.protocol == 6 || pkt.protocol == 17) && pkt.dport >= 1024) ||
              (pkt.protocol == 1 && scratch[20] == 0));
    } else if (n == ph_wg) {
        ok = !fw.direct_enabled && fw.uplink_ready && fw.tunnel_ready &&
             pkt.dst == lwip_ntohl(netif_ip4_addr(n)->addr);
    }
    if (ok) {
        if (!fw.direct_enabled && ph_wg && pkt.protocol == 6) {
            if (!ph_tcp_clamp_mss(scratch, p->tot_len, ph_wg->mtu))
                goto drop;
            if (pbuf_take(p, scratch, p->tot_len) != ERR_OK)
                goto drop;
        }
        return 0;
    }
drop:
    fw.blocked++;
    pbuf_free(p);
    return 1;
}
static netif_linkoutput_fn eth_linkoutput, sta_linkoutput;
static err_t guarded_eth_output(struct netif *n, struct pbuf *p) {
    if (!fw.direct_enabled || !same(n, ph_selected)) {
        uint8_t b[1514];
        if (p->tot_len > sizeof b || p->tot_len < 14)
            return ERR_IF;
        pbuf_copy_partial(p, b, p->tot_len, 0);
        unsigned type = ((unsigned)b[12] << 8) | b[13];
        if (type == 0x800) {
            ph_packet pkt;
            if (!ph_parse_ipv4(b + 14, p->tot_len - 14, &pkt))
                return ERR_IF;
            bool dhcp = pkt.protocol == 17 && pkt.sport == 68 && pkt.dport == 67;
            bool encrypted = same(n, ph_selected) && pkt.protocol == 17 &&
                             ph_vpn_outer_tx(pkt.dst, pkt.sport, pkt.dport);
            if (!dhcp && !encrypted) {
                fw.blocked++;
                return ERR_IF;
            }
        } else if (type != 0x806)
            return ERR_IF;
    }
    netif_linkoutput_fn output = same(n, ph_eth) ? eth_linkoutput : sta_linkoutput;
    return output ? output(n, p) : ERR_IF;
}
struct netif *ph_route(const ip4_addr_t *src, const ip4_addr_t *dst) {
    uint32_t dest = lwip_ntohl(dst->addr);
    if (ph_usb && (dest & 0xffffff00) == 0xc0a80700)
        return esp_netif_get_netif_impl(ph_usb);
    if (ph_ap && (dest & 0xffffff00) == 0xc0a80800)
        return esp_netif_get_netif_impl(ph_ap);
    if (src && client_addr(lwip_ntohl(src->addr))) {
        if (!fw.direct_enabled && ph_wg)
            return ph_wg;
        return ph_selected ? esp_netif_get_netif_impl(ph_selected) : NULL;
    }
    return NULL;
}
int ph_canforward(struct pbuf *p, unsigned long address) {
    struct netif *in = ip_current_input_netif();
    if (!fw.uplink_ready)
        return 0;
    if (same(in, ph_usb) || same(in, ph_ap)) {
        if (!fw.direct_enabled && !ph_vpn_up())
            return 0;
    } else if (in == ph_wg) {
        if (fw.direct_enabled || !ph_vpn_up())
            return 0;
    } else if (same(in, ph_selected)) {
        if (!fw.direct_enabled)
            return 0;
    } else
        return 0;
    return -1;
}
static void guard(esp_netif_t *e, netif_linkoutput_fn *previous) {
    LOCK_TCPIP_CORE();
    struct netif *n = esp_netif_get_netif_impl(e);
    if (n->linkoutput != guarded_eth_output) {
        *previous = n->linkoutput;
        n->linkoutput = guarded_eth_output;
    }
    UNLOCK_TCPIP_CORE();
}
void ph_gateway_guard_eth(void) {
    guard(ph_eth, &eth_linkoutput);
}
void ph_gateway_guard_sta(void) {
    guard(ph_sta, &sta_linkoutput);
}
void ph_gateway_ap_started(void) {
    LOCK_TCPIP_CORE();
    flush_nat();
    UNLOCK_TCPIP_CORE();
}
static void free_rx(void *h, void *p) {
    free(p);
}
static esp_err_t usb_tx(void *h, void *buf, size_t len) {
    if (!tud_ready() || tud_suspended() || len > 1514)
        return ESP_ERR_INVALID_STATE;
    void *copy = malloc(len);
    if (!copy)
        return ESP_ERR_NO_MEM;
    memcpy(copy, buf, len);
    esp_err_t e = tinyusb_net_send_sync(copy, len, NULL, pdMS_TO_TICKS(10));
    /* sync waits for the copy/lifetime barrier even on timeout. Caller alone owns this buffer. */
    free(copy);
    return e;
}
static esp_err_t usb_rx(void *buf, uint16_t len, void *ctx) {
    const uint8_t *b = buf;
    if (len < 14 || len > 1514)
        return ESP_OK;
    /* Only IPv4 and ARP. No VLAN bypass or IPv6 on the protected link. */
    unsigned type = ((unsigned)b[12] << 8) | b[13];
    if (type != 0x800 && type != 0x806)
        return ESP_OK;
    if (type == 0x806 && (len < 42 || b[14] != 0 || b[15] != 1 || b[16] != 8 || b[17] != 0 ||
                          b[18] != 6 || b[19] != 4))
        return ESP_OK;
    void *copy = malloc(len);
    if (!copy)
        return ESP_ERR_NO_MEM;
    memcpy(copy, buf, len);
    return esp_netif_receive(ph_usb, copy, len, NULL); /* stack owns/free callback */
}
static void usb_event(tinyusb_event_t *e, void *arg) {
    if (e->id == TINYUSB_EVENT_ATTACHED)
        esp_netif_action_connected(ph_usb, NULL, 0, NULL);
    else
        esp_netif_action_disconnected(ph_usb, NULL, 0, NULL);
}
/* NCM only. Prototype VID/PID from Espressif defaults; allocate a product identity before shipping.
 */
static const uint8_t fs_desc[] = {TUD_CONFIG_DESCRIPTOR(1, 2, 0,
                                                        TUD_CONFIG_DESC_LEN + TUD_CDC_NCM_DESC_LEN,
                                                        TUSB_DESC_CONFIG_ATT_SELF_POWERED, 0),
                                  TUD_CDC_NCM_DESCRIPTOR(0, 4, 5, 0x81, 64, 2, 0x82, 64, 1514)};
static const uint8_t hs_desc[] = {TUD_CONFIG_DESCRIPTOR(1, 2, 0,
                                                        TUD_CONFIG_DESC_LEN + TUD_CDC_NCM_DESC_LEN,
                                                        TUSB_DESC_CONFIG_ATT_SELF_POWERED, 0),
                                  TUD_CDC_NCM_DESCRIPTOR(0, 4, 5, 0x81, 64, 2, 0x82, 512, 1514)};
static char usb_serial[13];
static const char *usb_strings[] = {
    "\x09\x04", "Phoenix Lab", "Phoenix NCM", usb_serial, "USB network", "", NULL};
void ph_gateway_start(void) {
    ph_selected = ph_eth;
    fw.rules[0] = (ph_rule){.ingress = PH_USB,
                            .direction = PH_LOCAL,
                            .protocol = 6,
                            .port_first = 80,
                            .port_last = 80,
                            .allow = true};
    fw.rules[1] = (ph_rule){.ingress = PH_USB, .direction = PH_FORWARD, .allow = true};
    fw.rules[2] = (ph_rule){.ingress = PH_AP, .direction = PH_FORWARD, .allow = true};
    fw.rule_count = 3;
    if (!CONFIG_PHOENIX_USB_LAB) {
        ESP_LOGW("gateway", "USB held off: electrical fixture not approved");
        return;
    }
    if (CONFIG_PHOENIX_VBUS_GPIO != 5) {
        ESP_LOGE("gateway", "USB requires verified host VBUS sensing on reserved P1 GPIO5");
        return;
    }
    esp_netif_ip_info_t ip = {0};
    IP4_ADDR(&ip.ip, 192, 168, 7, 1);
    IP4_ADDR(&ip.gw, 192, 168, 7, 1);
    IP4_ADDR(&ip.netmask, 255, 255, 255, 0);
    esp_netif_inherent_config_t base = ESP_NETIF_INHERENT_DEFAULT_ETH();
    base.flags = ESP_NETIF_DHCP_SERVER | ESP_NETIF_FLAG_AUTOUP;
    base.ip_info = &ip;
    base.if_key = "USB";
    base.if_desc = "usb";
    base.route_prio = 0;
    base.get_ip_event = 0;
    base.lost_ip_event = 0;
    esp_netif_driver_ifconfig_t driver = {.transmit = usb_tx, .driver_free_rx_buffer = free_rx};
    esp_netif_config_t c = {
        .base = &base, .driver = &driver, .stack = ESP_NETIF_NETSTACK_DEFAULT_ETH};
    ph_usb = esp_netif_new(&c);
    ESP_ERROR_CHECK(ph_usb ? ESP_OK : ESP_ERR_NO_MEM);
    uint8_t mac[6];
    ESP_ERROR_CHECK(esp_read_mac(mac, ESP_MAC_ETH));
    mac[0] |= 2;
    mac[5] ^= 0x80;
    ESP_ERROR_CHECK(esp_netif_set_mac(ph_usb, mac));
    esp_netif_dns_info_t dns = {.ip.type = ESP_IPADDR_TYPE_V4};
    IP4_ADDR(&dns.ip.u_addr.ip4, 1, 1, 1, 1);
    ESP_ERROR_CHECK(esp_netif_set_dns_info(ph_usb, ESP_NETIF_DNS_MAIN, &dns));
    dhcps_offer_t offer = OFFER_DNS;
    ESP_ERROR_CHECK(esp_netif_dhcps_option(ph_usb, ESP_NETIF_OP_SET, ESP_NETIF_DOMAIN_NAME_SERVER,
                                           &offer, sizeof offer));
    esp_netif_action_start(ph_usb, NULL, 0, NULL);
    ESP_ERROR_CHECK(esp_netif_napt_enable(ph_usb));
    tinyusb_config_t tc = TINYUSB_DEFAULT_CONFIG(usb_event, NULL);
    tc.phy.self_powered = true;
    tc.phy.vbus_monitor_io = CONFIG_PHOENIX_VBUS_GPIO;
    snprintf(usb_serial, sizeof usb_serial, "%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2],
             mac[3], mac[4], mac[5]);
    tc.descriptor.full_speed_config = fs_desc;
    tc.descriptor.high_speed_config = hs_desc;
    tc.descriptor.string = usb_strings;
    tc.descriptor.string_count = 6;
    ESP_ERROR_CHECK(tinyusb_driver_install(&tc));
    tinyusb_net_config_t nc = {.on_recv_callback = usb_rx};
    memcpy(nc.mac_addr, mac, 6);
    ESP_ERROR_CHECK(tinyusb_net_init(&nc));
}
