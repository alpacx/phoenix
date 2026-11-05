#include "admin.h"
#include "cJSON.h"
#include "driver/uart.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "gateway.h"
#include "lwip/tcpip.h"
#include "mbedtls/sha256.h"
#include "nvs.h"
#include "vpn.h"
#include "wifi_manager.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
static uint8_t digest[32];
static bool paired;
static SemaphoreHandle_t mutex;
static const char page[] =
    "<!doctype html><html lang=it><meta charset=utf-8><meta name=viewport "
    "content='width=device-width,initial-scale=1'><title>Phoenix</title>"
    "<style>body{font:17px system-ui;max-width:48rem;margin:5vh "
    "auto;padding:1rem;background:#102029;color:#e2f4ed}button,input{font:inherit;padding:.7rem;"
    "margin:.4rem "
    "0;max-width:95%}button{cursor:pointer}pre{white-space:pre-wrap;background:#20343e;padding:"
    "1rem}label{display:block}</style>"
    "<h1>Phoenix · laboratorio</h1><p>Il dispositivo controlla solo il traffico che lo attraversa. "
    "IPv6 bloccato. WireGuard sperimentale; Wi-Fi STA/AP sperimentale.</p>"
    "<label>Token amministrativo <input id=t type=password autocomplete=off "
    "size=50></label><button id=s>Leggi stato</button> <button id=b>Blocca inoltro</button> "
    "<button id=d>Abilita Internet diretto</button><pre id=o>Pairing tramite seriale nei primi 120 "
    "secondi dall’avvio.</pre>"
    "<script>async function call(path,body){try{let r=await "
    "fetch('/api/v1/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer "
    "'+t.value,'Content-Type':'application/"
    "json'},body:body&&JSON.stringify(body)});o.textContent=JSON.stringify(await "
    "r.json(),null,2)}catch(e){o.textContent='Richiesta "
    "fallita'}}s.onclick=()=>call('status');b.onclick=()=>call('mode',{direct:false});d.onclick=()="
    ">{if(confirm('Consenti traffico senza VPN? Le sessioni possono "
    "interrompersi.'))call('mode',{direct:true})}</script></html>";
static esp_err_t reply(httpd_req_t *r, const char *status, const char *body) {
    httpd_resp_set_status(r, status);
    httpd_resp_set_type(r, "application/json");
    httpd_resp_set_hdr(r, "Cache-Control", "no-store");
    return httpd_resp_sendstr(r, body);
}
static bool auth(httpd_req_t *r) {
    char token[72];
    if (httpd_req_get_hdr_value_len(r, "Authorization") != 71 ||
        httpd_req_get_hdr_value_str(r, "Authorization", token, sizeof token) != ESP_OK ||
        memcmp(token, "Bearer ", 7))
        return false;
    uint8_t hash[32];
    mbedtls_sha256((uint8_t *)token + 7, 64, hash, 0);
    memset(token, 0, sizeof token);
    xSemaphoreTake(mutex, portMAX_DELAY);
    unsigned diff = paired ? 0 : 1;
    for (size_t i = 0; i < 32; i++)
        diff |= hash[i] ^ digest[i];
    xSemaphoreGive(mutex);
    memset(hash, 0, sizeof hash);
    return diff == 0;
}
static esp_err_t index_page(httpd_req_t *r) {
    httpd_resp_set_type(r, "text/html");
    httpd_resp_set_hdr(r, "Cache-Control", "no-store");
    httpd_resp_set_hdr(r, "X-Frame-Options", "DENY");
    return httpd_resp_sendstr(r, page);
}
static esp_err_t status(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    ph_firewall f;
    ph_gateway_snapshot(&f);
    ph_network_status net;
    ph_gateway_network_status(&net);
    char out[768];
#define JSON_BOOL(x) ((x) ? "true" : "false")
    snprintf(out, sizeof out,
             "{\"api_version\":1,\"uplink\":\"%s\",\"uplink_ready\":%s,"
             "\"ethernet_link\":%s,\"ethernet_ip\":%s,\"wifi_link\":%s,\"wifi_ip\":%s,"
             "\"ap_active\":%s,\"usb_configured\":%s,\"usb_mounted\":%s,\"usb_suspended\":%s,"
             "\"direct\":%s,\"vpn_up\":%s,\"allowed\":%llu,\"blocked\":%llu,\"malformed\":%llu,"
             "\"heap_free\":%lu,\"uptime_ms\":%lld}",
             net.selected_wifi ? "wifi" : "ethernet", JSON_BOOL(f.uplink_ready),
             JSON_BOOL(net.ethernet_link), JSON_BOOL(net.ethernet_ip), JSON_BOOL(net.wifi_link),
             JSON_BOOL(net.wifi_ip), JSON_BOOL(net.ap_active), JSON_BOOL(ph_usb),
             JSON_BOOL(net.usb_mounted), JSON_BOOL(net.usb_suspended), JSON_BOOL(f.direct_enabled),
             JSON_BOOL(f.tunnel_ready), f.allowed, f.blocked, f.malformed,
             (unsigned long)esp_get_free_heap_size(), esp_timer_get_time() / 1000);
#undef JSON_BOOL
    return reply(r, "200 OK", out);
}
static esp_err_t mode(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    char origin[64];
    size_t ol = httpd_req_get_hdr_value_len(r, "Origin");
    if (ol && (ol >= sizeof origin ||
               httpd_req_get_hdr_value_str(r, "Origin", origin, sizeof origin) != ESP_OK ||
               strcmp(origin, "http://192.168.7.1")))
        return reply(r, "403 Forbidden", "{\"error\":\"origin\"}");
    if (r->content_len < 2 || r->content_len > 64)
        return reply(r, "400 Bad Request", "{\"error\":\"size\"}");
    char body[65];
    size_t have = 0;
    while (have < r->content_len) {
        int n = httpd_req_recv(r, body + have, r->content_len - have);
        if (n <= 0)
            return ESP_FAIL;
        have += n;
    }
    body[have] = 0;
    const char *end = NULL;
    cJSON *obj = cJSON_ParseWithOpts(body, &end, true);
    cJSON *d = cJSON_GetObjectItemCaseSensitive(obj, "direct");
    if (!cJSON_IsObject(obj) || cJSON_GetArraySize(obj) != 1 || !cJSON_IsBool(d)) {
        cJSON_Delete(obj);
        return reply(r, "400 Bad Request", "{\"error\":\"expected_direct_boolean\"}");
    }
    ph_gateway_direct(cJSON_IsTrue(d));
    cJSON_Delete(obj);
    return reply(r, "200 OK", "{\"ok\":true}");
}
static esp_err_t vpn_import(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    if (httpd_req_get_hdr_value_len(r, "Origin"))
        return reply(r, "403 Forbidden", "{\"error\":\"use_local_client\"}");
    if (r->content_len < 1 || r->content_len > 4096)
        return reply(r, "400 Bad Request", "{\"error\":\"size\"}");
    char *body = calloc(1, r->content_len + 1);
    if (!body)
        return ESP_ERR_NO_MEM;
    size_t have = 0;
    while (have < r->content_len) {
        int n = httpd_req_recv(r, body + have, r->content_len - have);
        if (n <= 0) {
            memset(body, 0, r->content_len);
            free(body);
            return ESP_FAIL;
        }
        have += n;
    }
    ph_wg_profile profile;
    bool valid = ph_wg_parse(body, have, &profile);
    memset(body, 0, have);
    free(body);
    if (!valid)
        return reply(r, "400 Bad Request", "{\"error\":\"unsupported_or_malformed_profile\"}");
    ph_gateway_direct(false);
    LOCK_TCPIP_CORE();
    bool started = ph_vpn_start(&profile);
    UNLOCK_TCPIP_CORE();
    if (started && (ph_usb || ph_ap)) {
        esp_netif_dns_info_t dns = {0};
        dns.ip.type = ESP_IPADDR_TYPE_V4;
        esp_netif_str_to_ip4(profile.dns, &dns.ip.u_addr.ip4);
        if (ph_usb)
            esp_netif_set_dns_info(ph_usb, ESP_NETIF_DNS_MAIN, &dns);
        if (ph_ap)
            esp_netif_set_dns_info(ph_ap, ESP_NETIF_DNS_MAIN, &dns);
    }
    memset(&profile, 0, sizeof profile);
    return reply(r, started ? "202 Accepted" : "409 Conflict",
                 started ? "{\"state\":\"connecting\",\"renew_dhcp\":true}"
                         : "{\"error\":\"clock_uplink_or_vpn_init\",\"forwarding\":\"blocked\"}");
}
static bool local_origin(httpd_req_t *r) {
    char origin[64];
    size_t n = httpd_req_get_hdr_value_len(r, "Origin");
    return !n || (n < sizeof origin &&
                  httpd_req_get_hdr_value_str(r, "Origin", origin, sizeof origin) == ESP_OK &&
                  !strcmp(origin, "http://192.168.7.1"));
}
static cJSON *small_json(httpd_req_t *r) {
    if (r->content_len < 2 || r->content_len > 256)
        return NULL;
    char b[257];
    size_t have = 0;
    while (have < r->content_len) {
        int n = httpd_req_recv(r, b + have, r->content_len - have);
        if (n <= 0)
            return NULL;
        have += n;
    }
    b[have] = 0;
    cJSON *obj = cJSON_ParseWithOpts(b, NULL, true);
    memset(b, 0, sizeof b);
    return obj;
}
static esp_err_t uplink(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    if (!local_origin(r))
        return reply(r, "403 Forbidden", "{\"error\":\"origin\"}");
    cJSON *o = small_json(r), *v = cJSON_GetObjectItemCaseSensitive(o, "uplink");
    bool valid = cJSON_IsObject(o) && cJSON_GetArraySize(o) == 1 && cJSON_IsString(v) &&
                 (!strcmp(v->valuestring, "ethernet") || !strcmp(v->valuestring, "wifi"));
    if (!valid) {
        cJSON_Delete(o);
        return reply(r, "400 Bad Request", "{\"error\":\"uplink\"}");
    }
    esp_err_t e = ph_gateway_select(!strcmp(v->valuestring, "wifi"));
    cJSON_Delete(o);
    return reply(r, e == ESP_OK ? "200 OK" : "409 Conflict",
                 e == ESP_OK ? "{\"forwarding\":\"blocked\",\"ok\":true}"
                             : "{\"error\":\"interface_not_initialized\"}");
}
#if CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT
static void ota_restart(void *arg) {
    esp_restart();
}
#endif
static esp_err_t ota_upload(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    if (httpd_req_get_hdr_value_len(r, "Origin"))
        return reply(r, "403 Forbidden", "{\"error\":\"use_local_client\"}");
#if !CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT
    return reply(r, "503 Service Unavailable", "{\"error\":\"signed_build_required\"}");
#else
    const esp_partition_t *target = esp_ota_get_next_update_partition(NULL);
    if (!target || r->content_len < 4096 || r->content_len > target->size)
        return reply(r, "400 Bad Request", "{\"error\":\"image_size\"}");
    uint8_t *buffer = malloc(4096);
    if (!buffer)
        return ESP_ERR_NO_MEM;
    /* Keep traffic blocked after success or failure; never resume implicitly. */
    ph_gateway_direct(false);
    esp_ota_handle_t handle = 0;
    esp_err_t e = esp_ota_begin(target, r->content_len, &handle);
    size_t received = 0;
    int64_t deadline = esp_timer_get_time() + 120000000;
    while (e == ESP_OK && received < r->content_len) {
        size_t remaining = r->content_len - received;
        int n = httpd_req_recv(r, (char *)buffer, remaining < 4096 ? remaining : 4096);
        if (n <= 0 || esp_timer_get_time() > deadline) {
            e = ESP_ERR_TIMEOUT;
            break;
        }
        e = esp_ota_write(handle, buffer, n);
        received += n;
    }
    free(buffer);
    if (e != ESP_OK) {
        if (handle)
            esp_ota_abort(handle);
    } else {
        /* IDF verifies image integrity AND RSA signature against the running signed app. */
        e = esp_ota_end(handle);
    }
    esp_app_desc_t desc;
    if (e == ESP_OK) {
        e = esp_ota_get_partition_description(target, &desc);
        if (e == ESP_OK && strcmp(desc.project_name, "phoenix"))
            e = ESP_ERR_INVALID_ARG;
    }
    esp_timer_handle_t restart = NULL;
    if (e == ESP_OK) {
        const esp_timer_create_args_t timer = {.callback = ota_restart, .name = "ota_reboot"};
        e = esp_timer_create(&timer, &restart);
    }
    bool selected = false;
    if (e == ESP_OK) {
        e = esp_ota_set_boot_partition(target);
        selected = e == ESP_OK;
    }
    if (e == ESP_OK)
        e = esp_timer_start_once(restart, 1000000);
    if (e != ESP_OK) {
        if (restart)
            esp_timer_delete(restart);
        /* If scheduling failed after boot selection, restore the current slot. */
        if (selected)
            esp_ota_set_boot_partition(esp_ota_get_running_partition());
        httpd_resp_set_hdr(r, "Connection", "close");
        reply(r, "400 Bad Request", "{\"error\":\"update_rejected\",\"forwarding\":\"blocked\"}");
        return ESP_FAIL;
    }
    return reply(r, "202 Accepted",
                 "{\"status\":\"verified_rebooting\",\"forwarding\":\"blocked\"}");
#endif
}
static esp_err_t wifi_scan(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    wifi_ap_record_t records[16];
    uint16_t count = 16;
    esp_err_t e = ph_wifi_scan(records, &count);
    if (e != ESP_OK)
        return reply(r, "503 Service Unavailable", "{\"error\":\"scan_unavailable\"}");
    cJSON *root = cJSON_CreateObject();
    if (!root)
        return ESP_ERR_NO_MEM;
    cJSON *list = cJSON_AddArrayToObject(root, "networks");
    if (!list) {
        cJSON_Delete(root);
        return ESP_ERR_NO_MEM;
    }
    for (unsigned i = 0; i < count; i++) {
        cJSON *item = cJSON_CreateObject();
        char ssid[33];
        memcpy(ssid, records[i].ssid, 32);
        ssid[32] = 0;
        cJSON_AddStringToObject(item, "ssid", ssid);
        cJSON_AddNumberToObject(item, "rssi", records[i].rssi);
        cJSON_AddNumberToObject(item, "channel", records[i].primary);
        cJSON_AddItemToArray(list, item);
    }
    char *text = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (!text)
        return ESP_ERR_NO_MEM;
    esp_err_t result = reply(r, "200 OK", text);
    free(text);
    return result;
}
static esp_err_t wifi_configure(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    if (!local_origin(r))
        return reply(r, "403 Forbidden", "{\"error\":\"origin\"}");
    cJSON *o = small_json(r), *m = cJSON_GetObjectItemCaseSensitive(o, "mode"),
          *s = cJSON_GetObjectItemCaseSensitive(o, "ssid"),
          *p = cJSON_GetObjectItemCaseSensitive(o, "password"),
          *sv = cJSON_GetObjectItemCaseSensitive(o, "save"),
          *saved = cJSON_GetObjectItemCaseSensitive(o, "saved");
    bool ap = cJSON_IsString(m) && !strcmp(m->valuestring, "ap");
    bool mode_ok = cJSON_IsString(m) && (ap || !strcmp(m->valuestring, "sta"));
    bool use_saved = cJSON_IsTrue(saved) && !ap && cJSON_GetArraySize(o) == 2;
    bool fresh = cJSON_IsString(s) && cJSON_IsString(p) && !saved && (!sv || cJSON_IsBool(sv)) &&
                 cJSON_GetArraySize(o) == (sv ? 4 : 3) && !(ap && cJSON_IsTrue(sv));
    if (!mode_ok || (!use_saved && !fresh)) {
        cJSON_Delete(o);
        return reply(r, "400 Bad Request", "{\"error\":\"wifi_configuration\"}");
    }
    esp_err_t e = ph_wifi_configure(ap, fresh ? s->valuestring : NULL,
                                    fresh ? p->valuestring : NULL, cJSON_IsTrue(sv), use_saved);
    if (cJSON_IsString(p))
        memset(p->valuestring, 0, strlen(p->valuestring));
    cJSON_Delete(o);
    return reply(r, e == ESP_OK ? "202 Accepted" : "409 Conflict",
                 e == ESP_OK ? "{\"ok\":true,\"forwarding\":\"blocked\",\"ap_max_clients\":1}"
                             : "{\"error\":\"wifi_configuration_failed\"}");
}
/* Provision over local UART only. No token is printed, echoed or accepted over the uplink. */
static void serial_pair(void *arg) {
    char line[80];
    size_t n = 0;
    bool overflow = false;
    while (esp_timer_get_time() < 120000000) {
        uint8_t byte;
        if (uart_read_bytes(CONFIG_ESP_CONSOLE_UART_NUM, &byte, 1, pdMS_TO_TICKS(20)) != 1)
            continue;
        int ch = byte;
        if (ch == '\n' || ch == '\r') {
            if (!overflow && n == 15 && !memcmp(line, "time ", 5)) {
                bool valid = true;
                for (size_t i = 5; i < 15; i++)
                    if (line[i] < '0' || line[i] > '9')
                        valid = false;
                if (valid) {
                    line[15] = 0;
                    long long epoch = atoll(line + 5);
                    if (epoch >= 1700000000LL && epoch <= 4102444800LL) {
                        struct timeval tv = {.tv_sec = epoch};
                        settimeofday(&tv, NULL);
                        puts("Clock set");
                    }
                }
            }
            if (!overflow && n == 69 && !memcmp(line, "pair ", 5)) {
                bool valid = true;
                for (size_t i = 5; i < 69; i++)
                    if (!((line[i] >= '0' && line[i] <= '9') || (line[i] >= 'a' && line[i] <= 'f')))
                        valid = false;
                if (valid) {
                    uint8_t h[32];
                    mbedtls_sha256((uint8_t *)line + 5, 64, h, 0);
                    nvs_handle_t nv;
                    if (nvs_open("phoenix", NVS_READWRITE, &nv) == ESP_OK) {
                        esp_err_t e = nvs_set_blob(nv, "admin", h, 32);
                        if (e == ESP_OK)
                            e = nvs_set_u32(nv, "version", 1);
                        if (e == ESP_OK)
                            e = nvs_commit(nv);
                        nvs_close(nv);
                        if (e == ESP_OK) {
                            xSemaphoreTake(mutex, portMAX_DELAY);
                            memcpy(digest, h, 32);
                            paired = true;
                            xSemaphoreGive(mutex);
                            puts("Pairing saved");
                        }
                    }
                    memset(h, 0, sizeof h);
                }
            }
            memset(line, 0, sizeof line);
            n = 0;
            overflow = false;
        } else if (n < sizeof line)
            n++, line[n - 1] = (char)ch;
        else
            overflow = true;
    }
    memset(line, 0, sizeof line);
    vTaskDelete(NULL);
}
void ph_admin_start(void) {
    mutex = xSemaphoreCreateMutex();
    configASSERT(mutex);
    nvs_handle_t nv;
    if (nvs_open("phoenix", NVS_READONLY, &nv) == ESP_OK) {
        uint32_t version = 0;
        size_t len = 32;
        if (nvs_get_u32(nv, "version", &version) == ESP_OK && version == 1 &&
            nvs_get_blob(nv, "admin", digest, &len) == ESP_OK && len == 32)
            paired = true;
        nvs_close(nv);
    }
    ESP_LOGI("admin", "paired=%s schema=1", paired ? "yes" : "no");
    if (!uart_is_driver_installed(CONFIG_ESP_CONSOLE_UART_NUM))
        ESP_ERROR_CHECK(uart_driver_install(CONFIG_ESP_CONSOLE_UART_NUM, 1024, 0, 0, NULL, 0));
    configASSERT(xTaskCreate(serial_pair, "pair", 4096, NULL, 3, NULL) == pdPASS);
    if (!ph_usb)
        return;
    httpd_config_t c = HTTPD_DEFAULT_CONFIG();
    c.max_uri_handlers = 8;
    c.stack_size = 8192;
    c.recv_wait_timeout = 3;
    c.send_wait_timeout = 3;
    httpd_handle_t server;
    ESP_ERROR_CHECK(httpd_start(&server, &c));
    const httpd_uri_t routes[] = {
        {.uri = "/", .method = HTTP_GET, .handler = index_page},
        {.uri = "/api/v1/status", .method = HTTP_GET, .handler = status},
        {.uri = "/api/v1/mode", .method = HTTP_POST, .handler = mode},
        {.uri = "/api/v1/vpn", .method = HTTP_POST, .handler = vpn_import},
        {.uri = "/api/v1/uplink", .method = HTTP_POST, .handler = uplink},
        {.uri = "/api/v1/wifi", .method = HTTP_POST, .handler = wifi_configure},
        {.uri = "/api/v1/firmware", .method = HTTP_POST, .handler = ota_upload},
        {.uri = "/api/v1/wifi/scan", .method = HTTP_GET, .handler = wifi_scan}};
    for (size_t i = 0; i < sizeof routes / sizeof routes[0]; i++)
        ESP_ERROR_CHECK(httpd_register_uri_handler(server, &routes[i]));
}
