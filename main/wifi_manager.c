#include "wifi_manager.h"
#include "dhcpserver/dhcpserver.h"
#include "esp_event.h"
#include "esp_hosted.h"
#include "esp_log.h"
#include "esp_wifi_default.h"
#include "freertos/semphr.h"
#include "gateway.h"
#include "lwip/tcpip.h"
#include "nvs.h"
#include <stdatomic.h>
#include <string.h>
static SemaphoreHandle_t control;
static bool initialized, attempted;
static atomic_bool configured_sta;
static atomic_uint reconnects;
typedef struct {
    uint32_t version;
    char ssid[33];
    char password[64];
} stored_wifi;
static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT) {
        if (id == WIFI_EVENT_STA_START)
            ph_gateway_guard_sta();
        if (id == WIFI_EVENT_AP_START) {
            esp_err_t e = esp_netif_dhcps_start(ph_ap);
            if (e != ESP_OK && e != ESP_ERR_ESP_NETIF_DHCP_ALREADY_STARTED)
                ESP_LOGE("wifi", "AP DHCP start failed: %s", esp_err_to_name(e));
            ph_gateway_ap_started();
        }
        if (id == WIFI_EVENT_AP_STOP)
            ph_gateway_ap_started();
        if (id == WIFI_EVENT_STA_DISCONNECTED || id == WIFI_EVENT_STA_STOP) {
            ph_gateway_network_event(ph_sta, false);
            /* bounded retry; explicit new configuration resets retry budget */
            if (id == WIFI_EVENT_STA_DISCONNECTED && configured_sta && reconnects++ < 5)
                esp_wifi_connect();
        }
    }
    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        uint32_t m = e->ip_info.netmask.addr;
        esp_ip4_addr_t a, b;
        esp_netif_str_to_ip4("192.168.7.1", &a);
        esp_netif_str_to_ip4("192.168.8.1", &b);
        bool conflict =
            (e->ip_info.ip.addr & m) == (a.addr & m) || (e->ip_info.ip.addr & m) == (b.addr & m);
        ph_gateway_network_event(ph_sta, !conflict);
        reconnects = 0;
        ESP_LOGI("wifi", "STA DHCP received; subnet conflict=%d", conflict);
    }
    if (base == IP_EVENT && id == IP_EVENT_STA_LOST_IP)
        ph_gateway_network_event(ph_sta, false);
}
void ph_wifi_setup(void) {
    control = xSemaphoreCreateMutex();
    configASSERT(control);
}
/* Called with control lock. Netifs are created before event handlers so IDF defaults run first. */
static esp_err_t initialize(void) {
    if (initialized)
        return ESP_OK;
    if (attempted)
        return ESP_ERR_INVALID_STATE;
    attempted = true;
    esp_err_t e = esp_hosted_init();
    if (e != ESP_OK)
        return e;
    e = esp_hosted_connect_to_slave();
    if (e != ESP_OK)
        return e;
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    e = esp_wifi_init(&cfg);
    if (e != ESP_OK)
        return e;
    e = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    if (e != ESP_OK)
        return e;
    esp_netif_t *sta = esp_netif_create_default_wifi_sta();
    esp_netif_t *ap = esp_netif_create_default_wifi_ap();
    if (!sta || !ap)
        return ESP_ERR_NO_MEM;
    LOCK_TCPIP_CORE();
    ph_sta = sta;
    ph_ap = ap;
    UNLOCK_TCPIP_CORE();
    esp_netif_ip_info_t ip = {0};
    esp_netif_str_to_ip4("192.168.8.1", &ip.ip);
    ip.gw = ip.ip;
    esp_netif_str_to_ip4("255.255.255.0", &ip.netmask);
    esp_netif_dhcps_stop(ap);
    e = esp_netif_set_ip_info(ap, &ip);
    if (e != ESP_OK)
        return e;
    esp_netif_dns_info_t dns = {.ip.type = ESP_IPADDR_TYPE_V4};
    esp_netif_str_to_ip4("1.1.1.1", &dns.ip.u_addr.ip4);
    esp_netif_set_dns_info(ap, ESP_NETIF_DNS_MAIN, &dns);
    dhcps_offer_t offer = OFFER_DNS;
    esp_netif_dhcps_option(ap, ESP_NETIF_OP_SET, ESP_NETIF_DOMAIN_NAME_SERVER, &offer,
                           sizeof offer);
    e = esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL);
    if (e != ESP_OK)
        return e;
    e = esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL);
    if (e != ESP_OK)
        return e;
    initialized = true;
    return ESP_OK;
}
esp_err_t ph_wifi_initialize(void) {
    xSemaphoreTake(control, portMAX_DELAY);
    esp_err_t e = initialize();
    xSemaphoreGive(control);
    return e;
}
esp_err_t ph_wifi_scan(wifi_ap_record_t *records, uint16_t *count) {
    xSemaphoreTake(control, portMAX_DELAY);
    esp_err_t e = initialize();
    wifi_mode_t mode = WIFI_MODE_NULL;
    if (e == ESP_OK)
        e = esp_wifi_get_mode(&mode);
    if (e == ESP_OK && mode == WIFI_MODE_AP)
        e = ESP_ERR_INVALID_STATE; /* do not disrupt an active hotspot */
    if (e == ESP_OK && mode == WIFI_MODE_NULL)
        e = esp_wifi_set_mode(WIFI_MODE_STA);
    if (e == ESP_OK) {
        e = esp_wifi_start();
        if (e == ESP_ERR_WIFI_NOT_INIT)
            e = ESP_FAIL;
    }
    if (e == ESP_OK)
        e = esp_wifi_scan_start(NULL, true);
    if (e == ESP_OK)
        e = esp_wifi_scan_get_ap_records(count, records);
    esp_wifi_clear_ap_list();
    xSemaphoreGive(control);
    return e;
}
esp_err_t ph_wifi_configure(bool ap, const char *ssid, const char *password, bool save,
                            bool saved) {
    stored_wifi record = {.version = 1};
    if (saved) {
        nvs_handle_t n;
        esp_err_t e = nvs_open("phoenix", NVS_READONLY, &n);
        if (e != ESP_OK)
            return e;
        size_t size = sizeof record;
        e = nvs_get_blob(n, "wifi_sta", &record, &size);
        nvs_close(n);
        if (e != ESP_OK || size != sizeof record || record.version != 1 || record.ssid[32] ||
            record.password[63])
            return ESP_ERR_INVALID_STATE;
        ssid = record.ssid;
        password = record.password;
    }
    if (!ssid || !password || strlen(ssid) < 1 || strlen(ssid) > 32 || strlen(password) < 8 ||
        strlen(password) > 63)
        return ESP_ERR_INVALID_ARG;
    if (!saved) {
        strcpy(record.ssid, ssid);
        strcpy(record.password, password);
    }
    xSemaphoreTake(control, portMAX_DELAY);
    esp_err_t e = initialize();
    if (e == ESP_OK) {
        ph_gateway_direct(false);
        configured_sta = false;
        reconnects = 0;
        esp_wifi_stop();
        e = esp_wifi_set_mode(ap ? WIFI_MODE_AP : WIFI_MODE_STA);
    }
    wifi_config_t cfg = {0};
    if (ap) {
        memcpy(cfg.ap.ssid, record.ssid, strlen(record.ssid));
        cfg.ap.ssid_len = strlen(record.ssid);
        strcpy((char *)cfg.ap.password, record.password);
        cfg.ap.channel = 6;
        cfg.ap.max_connection = 1;
        cfg.ap.authmode = WIFI_AUTH_WPA2_PSK;
        cfg.ap.pmf_cfg.capable = true;
    } else {
        memcpy(cfg.sta.ssid, record.ssid, strlen(record.ssid));
        strcpy((char *)cfg.sta.password, record.password);
        cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
        cfg.sta.pmf_cfg.capable = true;
    }
    if (e == ESP_OK)
        e = esp_wifi_set_config(ap ? WIFI_IF_AP : WIFI_IF_STA, &cfg);
    if (e == ESP_OK)
        e = esp_wifi_start();
    if (e == ESP_OK && !ap) {
        configured_sta = true;
        e = esp_wifi_connect();
    }
    if (e == ESP_OK && save && !ap) {
        nvs_handle_t n;
        e = nvs_open("phoenix", NVS_READWRITE, &n);
        if (e == ESP_OK) {
            e = nvs_set_blob(n, "wifi_sta", &record, sizeof record);
            if (e == ESP_OK)
                e = nvs_commit(n);
            nvs_close(n);
        }
    }
    memset(&cfg, 0, sizeof cfg);
    memset(&record, 0, sizeof record);
    xSemaphoreGive(control);
    return e;
}
