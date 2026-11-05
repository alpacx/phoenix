#pragma once
#include "esp_netif.h"
#include "phoenix.h"
extern esp_netif_t *ph_usb, *ph_eth, *ph_sta, *ph_ap, *ph_selected;
void ph_gateway_start(void);
void ph_gateway_direct(bool enabled);
void ph_gateway_uplink(bool ready);
void ph_gateway_snapshot(ph_firewall *out);

void ph_gateway_guard_eth(void);

void ph_gateway_network_event(esp_netif_t *net, bool ready);
esp_err_t ph_gateway_select(bool wifi);
void ph_gateway_guard_sta(void);
void ph_gateway_ap_started(void);

typedef struct {
    bool ethernet_link, ethernet_ip, wifi_link, wifi_ip, ap_active;
    bool usb_mounted, usb_suspended;
    bool selected_wifi;
} ph_network_status;
void ph_gateway_network_status(ph_network_status *out);
