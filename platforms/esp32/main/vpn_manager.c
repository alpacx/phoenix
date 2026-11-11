#include "vpn_manager.h"
#include "build_epoch.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "gateway.h"
#include "lwip/dns.h"
#include "lwip/netdb.h"
#include "lwip/sockets.h"
#include "lwip/tcpip.h"
#include "mbedtls/platform_util.h"
#include "nord_countries.h"
#include "nvs.h"
#include "vpn.h"
#include "vpn_history.h"
#include "vpn_rotation.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

typedef struct {
    uint32_t version;
    char provider[12], country[3];
    bool enabled, rotation, direct, exclude_restricted;
    uint32_t interval;
    ph_wg_profile profile;
    char nord_key[45];
} settings;
static settings cfg = {.version = 2, .interval = 300};
static SemaphoreHandle_t mutex;
static QueueHandle_t commands;
static char state[32] = "idle", error[64], server_name[64], server_country[3];
static uint32_t server_id = UINT32_MAX;
static int64_t next_rotation, attempt_at, connected_at;
static size_t previous_country = SIZE_MAX;
static bool pending;
static bool api_verified;
static bool clock_verified;
static char exit_ip[16], exit_country[3];
static int64_t exit_checked;
static void wipe(void *p, size_t n) {
    mbedtls_platform_zeroize(p, n);
}
static const char *str(const cJSON *o, const char *key) {
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, key);
    return cJSON_IsString(v) ? v->valuestring : "";
}
static void status_set(const char *s, const char *e) {
    xSemaphoreTake(mutex, portMAX_DELAY);
    snprintf(state, sizeof state, "%s", s);
    snprintf(error, sizeof error, "%s", e ? e : "");
    xSemaphoreGive(mutex);
}
static bool save(const settings *s) {
    nvs_handle_t n;
    esp_err_t e = nvs_open("phoenix", NVS_READWRITE, &n);
    if (e != ESP_OK)
        return false;
    e = nvs_set_blob(n, "vpn_manager", s, sizeof *s);
    if (e == ESP_OK)
        e = nvs_commit(n);
    nvs_close(n);
    return e == ESP_OK;
}
static void assign(const settings *s) {
    xSemaphoreTake(mutex, portMAX_DELAY);
    cfg = *s;
    xSemaphoreGive(mutex);
}
static bool key_valid(const char *key) {
    if (strlen(key) != 44)
        return false;
    char text[400];
    ph_wg_profile p;
    snprintf(text, sizeof text,
             "[Interface]\nPrivateKey=%s\nAddress=10.5.0.2/"
             "32\nDNS=103.86.96.100\n[Peer]\nPublicKey=%s\nEndpoint=1.1.1.1:51820\nAllowedIPs=0.0."
             "0.0/0\n",
             key, key);
    bool ok = ph_wg_parse(text, strlen(text), &p);
    wipe(text, sizeof text);
    wipe(&p, sizeof p);
    return ok;
}
/* Fixed-host, verified TLS, no redirects, strict bounded body. No arbitrary URL
 * supplied by the browser. Control exceptions close on EVERY exit path. */
static esp_err_t response_header(esp_http_client_event_t *e) {
    if (e->event_id == HTTP_EVENT_ON_HEADER && !strcasecmp(e->header_key, "Date"))
        snprintf((char *)e->user_data, 64, "%s", e->header_value);
    return ESP_OK;
}
static cJSON *nord_get(const char *path, const char *token) {
    ip_addr_t dns;
    LOCK_TCPIP_CORE();
    dns = *dns_getserver(0);
    UNLOCK_TCPIP_CORE();
    if (ip_addr_isany(&dns)) {
        ipaddr_aton("1.1.1.1", &dns);
        LOCK_TCPIP_CORE();
        dns_setserver(0, &dns);
        UNLOCK_TCPIP_CORE();
    }
    ph_gateway_control(0, lwip_ntohl(ip_2_ip4(&dns)->addr));
    struct addrinfo hints = {.ai_family = AF_INET, .ai_socktype = SOCK_STREAM}, *ai = NULL;
    if (getaddrinfo("api.nordvpn.com", NULL, &hints, &ai) != 0) {
        ph_gateway_control(0, 0);
        return NULL;
    }
    struct sockaddr_in *a = (struct sockaddr_in *)ai->ai_addr;
    uint32_t ip = lwip_ntohl(a->sin_addr.s_addr);
    char address[16];
    inet_ntop(AF_INET, &a->sin_addr, address, sizeof address);
    freeaddrinfo(ai);
    ph_gateway_control(ip, 0);
    char url[384];
    snprintf(url, sizeof url, "https://%s%s", address, path);
    char date[64] = {0};
    esp_http_client_config_t hc = {.event_handler = response_header,
                                   .user_data = date,
                                   .url = url,
                                   .common_name = "api.nordvpn.com",
                                   .crt_bundle_attach = esp_crt_bundle_attach,
                                   .timeout_ms = 12000,
                                   .disable_auto_redirect = true,
                                   .buffer_size = 2048,
                                   .buffer_size_tx = 2048};
    if (token && *token) {
        hc.username = "token";
        hc.password = token;
        hc.auth_type = HTTP_AUTH_TYPE_BASIC;
    }
    esp_http_client_handle_t h = esp_http_client_init(&hc);
    cJSON *result = NULL;
    char *body = NULL;
    if (!h)
        goto done;
    esp_http_client_set_header(h, "Host", "api.nordvpn.com");
    esp_http_client_set_header(h, "Accept", "application/json");
    if (esp_http_client_open(h, 0) != ESP_OK)
        goto done;
    int64_t size = esp_http_client_fetch_headers(h);
    if (esp_http_client_get_status_code(h) != 200 || size > 49152)
        goto done;
    body = calloc(1, 49153);
    if (!body)
        goto done;
    size_t have = 0;
    int64_t deadline = esp_timer_get_time() + 20000000;
    while (have < 49152 && esp_timer_get_time() < deadline) {
        int n = esp_http_client_read(h, body + have, 49152 - have);
        if (n < 0)
            goto done;
        if (!n)
            break;
        have += n;
    }
    if (!esp_http_client_is_complete_data_received(h))
        goto done;
    body[have] = 0;
    result = cJSON_ParseWithOpts(body, NULL, true);
    /* Date is authenticated by TLS. It provides a fresh handshake timestamp on
     * reboot, without unauthenticated NTP changing the device clock. */
    if (*date) {
        struct tm tm = {0};
        if (strptime(date, "%a, %d %b %Y %H:%M:%S GMT", &tm)) {
            time_t t = mktime(&tm);
            if (t >= PH_BUILD_EPOCH) {
                struct timeval tv = {.tv_sec = t};
                settimeofday(&tv, NULL);
            }
        }
    }
done:
    if (body) {
        wipe(body, 49153);
        free(body);
    }
    if (h)
        esp_http_client_cleanup(h);
    ph_gateway_control(0, 0);
    return result;
}
static bool country_id(const char *code, unsigned *id) {
    for (size_t i = 0; i < sizeof nord_countries / sizeof *nord_countries; i++)
        if (!strcmp(code, nord_countries[i].code)) {
            *id = nord_countries[i].id;
            return true;
        }
    return false;
}
static bool nord_profile(const settings *s, ph_wg_profile *p) {
    unsigned cid;
    char country[3];
    if (*s->country) {
        if ((s->exclude_restricted && ph_vpn_country_restricted(s->country)) ||
            !country_id(s->country, &cid))
            return false;
        memcpy(country, s->country, 3);
    } else {
        size_t eligible[sizeof nord_countries / sizeof *nord_countries], count = 0,
                                                                         previous = SIZE_MAX;
        for (size_t j = 0; j < sizeof nord_countries / sizeof *nord_countries; j++) {
            if (s->exclude_restricted && ph_vpn_country_restricted(nord_countries[j].code))
                continue;
            if (j == previous_country)
                previous = count;
            eligible[count++] = j;
        }
        if (!count)
            return false;
        size_t i = eligible[ph_vpn_next_country(count, previous, esp_random())];
        cid = nord_countries[i].id;
        memcpy(country, nord_countries[i].code, 3);
    }
    char path[256];
    snprintf(path, sizeof path,
             "/v1/servers/"
             "recommendations?filters[servers_technologies][identifier]=wireguard_udp&filters["
             "country_id]=%u&limit=5",
             cid);
    cJSON *root = nord_get(path, NULL);
    if (!cJSON_IsArray(root)) {
        cJSON_Delete(root);
        return false;
    }
    ph_wg_profile candidates[5];
    ph_vpn_location locations[5];
    char names[5][64];
    size_t count = 0;
    cJSON *item;
    cJSON_ArrayForEach(item, root) {
        if (count == 5)
            break;
        cJSON *loc = cJSON_GetArrayItem(cJSON_GetObjectItemCaseSensitive(item, "locations"), 0);
        const char *code = str(cJSON_GetObjectItemCaseSensitive(loc, "country"), "code");
        if (strcmp(code, country) || strcmp(str(item, "status"), "online"))
            continue;
        const char *pub = "";
        cJSON *tech;
        cJSON_ArrayForEach(tech, cJSON_GetObjectItemCaseSensitive(item, "technologies")) {
            if (strcmp(str(tech, "identifier"), "wireguard_udp"))
                continue;
            cJSON *m;
            cJSON_ArrayForEach(m, cJSON_GetObjectItemCaseSensitive(
                                      tech, "metadata")) if (!strcmp(str(m, "name"), "public_key"))
                pub = str(m, "value");
        }
        cJSON *id = cJSON_GetObjectItemCaseSensitive(item, "id");
        if (!cJSON_IsNumber(id) || id->valuedouble < 1 || id->valuedouble >= UINT32_MAX)
            continue;
        char text[512];
        snprintf(text, sizeof text,
                 "[Interface]\nPrivateKey=%s\nAddress=10.5.0.2/"
                 "32\nDNS=103.86.96.100\nMTU=1380\n[Peer]\nPublicKey=%s\nEndpoint=%s:"
                 "51820\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=25\n",
                 s->nord_key, pub, str(item, "station"));
        bool valid = ph_wg_parse(text, strlen(text), &candidates[count]);
        wipe(text, sizeof text);
        if (!valid)
            continue;
        locations[count] = (ph_vpn_location){.id = (uint32_t)id->valuedouble};
        memcpy(locations[count].country, code, 3);
        snprintf(names[count], sizeof names[count], "%s", str(item, "name"));
        count++;
    }
    cJSON_Delete(root);
    uint32_t picked = ph_vpn_pick(locations, count, country, server_id, esp_random(), esp_random());
    bool found = false;
    for (size_t i = 0; i < count; i++)
        if (locations[i].id == picked) {
            *p = candidates[i];
            xSemaphoreTake(mutex, portMAX_DELAY);
            server_id = picked;
            memcpy(server_country, country, 3);
            for (size_t i = 0; i < sizeof nord_countries / sizeof *nord_countries; i++)
                if (!strcmp(country, nord_countries[i].code))
                    previous_country = i;
            snprintf(server_name, sizeof server_name, "%s", names[i]);
            xSemaphoreGive(mutex);
            found = true;
            break;
        }
    wipe(candidates, sizeof candidates);
    return found;
}
static void connect_now(void) {
    settings s;
    xSemaphoreTake(mutex, portMAX_DELAY);
    s = cfg;
    next_rotation = 0;
    connected_at = 0;
    exit_ip[0] = 0;
    exit_country[0] = 0;
    exit_checked = 0;
    server_name[0] = 0;
    server_country[0] = 0;
    xSemaphoreGive(mutex);
    ph_gateway_direct(false);
    status_set("connecting", NULL);
    if (!clock_verified && strcmp(s.provider, "nordvpn")) {
        cJSON *clock_response = nord_get(
            "/v1/servers/"
            "recommendations?filters[servers_technologies][identifier]=wireguard_udp&limit=1",
            NULL);
        cJSON_Delete(clock_response);
    }
    ph_wg_profile p = s.profile;
    bool valid = true;
    if (!strcmp(s.provider, "nordvpn"))
        valid = nord_profile(&s, &p);
    if (valid) {
        LOCK_TCPIP_CORE();
        valid = ph_vpn_start(&p);
        UNLOCK_TCPIP_CORE();
    }
    if (valid) {
        esp_netif_dns_info_t dns = {.ip.type = ESP_IPADDR_TYPE_V4};
        esp_netif_str_to_ip4(p.dns, &dns.ip.u_addr.ip4);
        if (ph_ap)
            esp_netif_set_dns_info(ph_ap, ESP_NETIF_DNS_MAIN, &dns);
        if (ph_usb)
            esp_netif_set_dns_info(ph_usb, ESP_NETIF_DNS_MAIN, &dns);
    } else
        status_set("blocked", !strcmp(s.provider, "nordvpn") ? "nord_server_or_api_unavailable"
                                                             : "vpn_start_failed");
    attempt_at = esp_timer_get_time();
    wipe(&p, sizeof p);
    wipe(&s, sizeof s);
}
/* Bound to the WireGuard netif: this measurement cannot silently use WAN.
 * It validates TLS against 1.1.1.1 and never opens the control-plane allowlist. */
static void verify_exit(void) {
    struct ifreq iface = {0};
    LOCK_TCPIP_CORE();
    bool up = ph_wg && ph_vpn_up();
    if (up)
        netif_index_to_name(netif_get_index(ph_wg), iface.ifr_name);
    UNLOCK_TCPIP_CORE();
    if (!up) {
        status_set("blocked", "vpn_required_for_exit_check");
        return;
    }
    esp_http_client_config_t hc = {.url = "https://1.1.1.1/cdn-cgi/trace",
                                   .crt_bundle_attach = esp_crt_bundle_attach,
                                   .timeout_ms = 10000,
                                   .disable_auto_redirect = true,
                                   .if_name = &iface,
                                   .buffer_size = 2048};
    esp_http_client_handle_t h = esp_http_client_init(&hc);
    char body[2048] = {0};
    bool valid = false;
    if (h && esp_http_client_open(h, 0) == ESP_OK) {
        int64_t size = esp_http_client_fetch_headers(h);
        if (size <= 2047 && esp_http_client_get_status_code(h) == 200) {
            int n = esp_http_client_read_response(h, body, sizeof body - 1);
            if (n > 0 && esp_http_client_is_complete_data_received(h)) {
                char *ip = strstr(body, "\nip="), *loc = strstr(body, "\nloc=");
                if (ip) {
                    ip += 4;
                    char *end = strchr(ip, '\n');
                    if (end)
                        *end = 0;
                    ip4_addr_t parsed;
                    if (strlen(ip) < sizeof exit_ip && ip4addr_aton(ip, &parsed)) {
                        xSemaphoreTake(mutex, portMAX_DELAY);
                        snprintf(exit_ip, sizeof exit_ip, "%s", ip);
                        exit_country[0] = 0;
                        if (loc && loc[5] >= 'A' && loc[5] <= 'Z' && loc[6] >= 'A' &&
                            loc[6] <= 'Z') {
                            exit_country[0] = loc[5];
                            exit_country[1] = loc[6];
                            exit_country[2] = 0;
                        }
                        exit_checked = esp_timer_get_time();
                        xSemaphoreGive(mutex);
                        valid = true;
                    }
                }
            }
        }
    }
    if (h)
        esp_http_client_cleanup(h);
    if (!valid)
        status_set("error", "exit_check_failed");
}
static void command_run(cJSON *o) {
    const char *action = str(o, "action");
    status_set("processing", NULL);
    settings s;
    xSemaphoreTake(mutex, portMAX_DELAY);
    s = cfg;
    xSemaphoreGive(mutex);
    bool change = true, reconnect = false;
    if (!strcmp(action, "wireguard")) {
        if (!ph_wg_parse(str(o, "profile"), strlen(str(o, "profile")), &s.profile)) {
            status_set("error", "invalid_wireguard_profile");
            goto done;
        }
        strcpy(s.provider, "wireguard");
        s.enabled = true;
        s.direct = false;
        s.rotation = false;
        reconnect = true;
    } else if (!strcmp(action, "nordvpn")) {
        const char *token = str(o, "token");
        if (*token) {
            status_set("provisioning", NULL);
            cJSON *r = nord_get("/v1/users/services/credentials", token);
            const char *key = str(r, "nordlynx_private_key");
            if (!key_valid(key)) {
                if (r) {
                    cJSON *v = cJSON_GetObjectItemCaseSensitive(r, "nordlynx_private_key");
                    if (cJSON_IsString(v))
                        wipe(v->valuestring, strlen(v->valuestring));
                    cJSON_Delete(r);
                }
                status_set("error", "nord_account_rejected_or_api_unavailable");
                goto done;
            }
            strcpy(s.nord_key, key);
            cJSON *v = cJSON_GetObjectItemCaseSensitive(r, "nordlynx_private_key");
            wipe(v->valuestring, strlen(v->valuestring));
            cJSON_Delete(r);
        }
        if (!key_valid(s.nord_key)) {
            status_set("error", "nord_token_required");
            goto done;
        }
        strcpy(s.provider, "nordvpn");
        strcpy(s.country, str(o, "country"));
        s.interval = cJSON_GetObjectItemCaseSensitive(o, "interval")->valueint;
        s.rotation = cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(o, "rotation"));
        cJSON *exclusion = cJSON_GetObjectItemCaseSensitive(o, "exclude_restricted");
        if (exclusion)
            s.exclude_restricted = cJSON_IsTrue(exclusion);
        if (s.exclude_restricted && ph_vpn_country_restricted(s.country)) {
            status_set("error", "country_excluded");
            goto done;
        }
        s.enabled = true;
        s.direct = false;
        reconnect = true;
    } else if (!strcmp(action, "connect")) {
        if (!*s.provider) {
            status_set("error", "profile_required");
            goto done;
        }
        s.enabled = true;
        s.direct = false;
        reconnect = true;
    } else if (!strcmp(action, "disconnect")) {
        s.enabled = false;
        s.direct = false;
    } else if (!strcmp(action, "direct")) {
        s.enabled = false;
        s.direct = true;
    } else if (!strcmp(action, "forget")) {
        wipe(&s, sizeof s);
        s.version = 2;
        s.interval = 300;
    } else if (!strcmp(action, "rotate")) {
        change = false;
        reconnect = s.enabled && !strcmp(s.provider, "nordvpn");
    } else if (!strcmp(action, "verify_exit")) {
        verify_exit();
        goto done;
    } else if (!strcmp(action, "catalog_test")) {
        change = false;
        cJSON *r = nord_get(
            "/v1/servers/"
            "recommendations?filters[servers_technologies][identifier]=wireguard_udp&limit=1",
            NULL);
        xSemaphoreTake(mutex, portMAX_DELAY);
        api_verified = cJSON_IsArray(r);
        xSemaphoreGive(mutex);
        status_set(cJSON_IsArray(r) ? "catalog_ok" : "error",
                   cJSON_IsArray(r) ? NULL : "nord_api_unavailable");
        cJSON_Delete(r);
        goto done;
    }
    if (change) {
        if (!save(&s)) {
            status_set("error", "storage_failed");
            goto done;
        }
        assign(&s);
    }
    if (reconnect)
        connect_now();
    else if (change) {
        ph_gateway_direct(s.direct);
        status_set(s.direct ? "direct" : "blocked", NULL);
        xSemaphoreTake(mutex, portMAX_DELAY);
        next_rotation = 0;
        connected_at = 0;
        exit_ip[0] = 0;
        exit_country[0] = 0;
        exit_checked = 0;
        xSemaphoreGive(mutex);
    }
done:
    wipe(&s, sizeof s);
}
static void run(void *unused) {
    for (;;) {
        cJSON *o = NULL;
        if (xQueueReceive(commands, &o, pdMS_TO_TICKS(1000)) == pdTRUE) {
            command_run(o);
            cJSON *token = cJSON_GetObjectItemCaseSensitive(o, "token"),
                  *profile = cJSON_GetObjectItemCaseSensitive(o, "profile");
            if (cJSON_IsString(token))
                wipe(token->valuestring, strlen(token->valuestring));
            if (cJSON_IsString(profile))
                wipe(profile->valuestring, strlen(profile->valuestring));
            cJSON_Delete(o);
            xSemaphoreTake(mutex, portMAX_DELAY);
            pending = false;
            xSemaphoreGive(mutex);
        }
        settings s;
        xSemaphoreTake(mutex, portMAX_DELAY);
        s = cfg;
        xSemaphoreGive(mutex);
        ph_firewall fw;
        ph_gateway_snapshot(&fw);
        int64_t now = esp_timer_get_time();
        if (s.direct && !fw.direct_enabled)
            ph_gateway_direct(true);
        if (s.enabled && *s.provider && fw.uplink_ready) {
            if (fw.tunnel_ready) {
                xSemaphoreTake(mutex, portMAX_DELAY);
                bool newly_connected = !connected_at;
                if (!connected_at) {
                    connected_at = now;
                    next_rotation = s.rotation && !strcmp(s.provider, "nordvpn")
                                        ? now + (int64_t)s.interval * 1000000
                                        : 0;
                }
                bool rotate = next_rotation && now >= next_rotation;
                strcpy(state, "connected");

                xSemaphoreGive(mutex);
                if (newly_connected && !strcmp(s.provider, "nordvpn"))
                    ph_history_add(server_country, server_name, server_id);
                if (rotate)
                    connect_now();
            } else if (now - attempt_at >= 30000000 || !attempt_at)
                connect_now();
        }
        wipe(&s, sizeof s);
    }
}
void ph_vpn_manager_init(void) {
    ph_history_init();
    mutex = xSemaphoreCreateMutex();
    commands = xQueueCreate(1, sizeof(cJSON *));
    configASSERT(mutex && commands);
    nvs_handle_t n;
    if (nvs_open("phoenix", NVS_READONLY, &n) == ESP_OK) {
        settings s;
        size_t size = sizeof s;
        if (nvs_get_blob(n, "vpn_manager", &s, &size) == ESP_OK && size == sizeof s &&
            (s.version == 1 || s.version == 2) && s.provider[11] == 0 && s.country[2] == 0 &&
            s.nord_key[44] == 0 && s.interval >= 30 && s.interval <= 86400 &&
            (!strcmp(s.provider, "wireguard") || !strcmp(s.provider, "nordvpn") || !*s.provider)) {
            if (s.version == 1)
                s.exclude_restricted = false;
            s.version = 2;
            cfg = s;
        }
        wipe(&s, sizeof s);
        nvs_close(n);
    }
    if (time(NULL) < PH_BUILD_EPOCH) {
        struct timeval tv = {.tv_sec = PH_BUILD_EPOCH};
        settimeofday(&tv, NULL);
    }
    configASSERT(xTaskCreate(run, "vpn_manager", 16384, NULL, 3, NULL) == pdPASS);
}
bool ph_vpn_manager_configured(void) {
    xSemaphoreTake(mutex, portMAX_DELAY);
    bool configured = *cfg.provider || cfg.direct;
    xSemaphoreGive(mutex);
    return configured;
}
void ph_vpn_manager_bench(const ph_wg_profile *p) {
    xSemaphoreTake(mutex, portMAX_DELAY);
    if (!*cfg.provider && !cfg.direct) {
        cfg.profile = *p;
        strcpy(cfg.provider, "wireguard");
        cfg.enabled = true;
    }
    xSemaphoreGive(mutex);
}
esp_err_t ph_vpn_manager_command(const cJSON *o) {
    if (!cJSON_IsObject(o))
        return ESP_ERR_INVALID_ARG;
    const char *a = str(o, "action");
    if (!strcmp(a, "nordvpn")) {
        cJSON *exclusion = cJSON_GetObjectItemCaseSensitive(o, "exclude_restricted");
        if (exclusion && !cJSON_IsBool(exclusion))
            return ESP_ERR_INVALID_ARG;
        xSemaphoreTake(mutex, portMAX_DELAY);
        bool excluded = exclusion ? cJSON_IsTrue(exclusion) : cfg.exclude_restricted;
        xSemaphoreGive(mutex);
        if (excluded && ph_vpn_country_restricted(str(o, "country")))
            return ESP_ERR_INVALID_ARG;
        cJSON *i = cJSON_GetObjectItemCaseSensitive(o, "interval"),
              *r = cJSON_GetObjectItemCaseSensitive(o, "rotation");
        unsigned cid;
        if (!ph_vpn_country_valid(str(o, "country"), true) ||
            (*str(o, "country") && !country_id(str(o, "country"), &cid)) || !cJSON_IsBool(r) ||
            !cJSON_IsNumber(i) || i->valuedouble != i->valueint || i->valueint < 30 ||
            i->valueint > 86400 || strlen(str(o, "token")) > 128)
            return ESP_ERR_INVALID_ARG;
    } else if (!strcmp(a, "wireguard")) {
        ph_wg_profile p;
        bool ok = ph_wg_parse(str(o, "profile"), strlen(str(o, "profile")), &p);
        wipe(&p, sizeof p);
        if (!ok)
            return ESP_ERR_INVALID_ARG;
    } else if (strcmp(a, "connect") && strcmp(a, "disconnect") && strcmp(a, "direct") &&
               strcmp(a, "rotate") && strcmp(a, "forget") && strcmp(a, "catalog_test") &&
               strcmp(a, "verify_exit"))
        return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(mutex, portMAX_DELAY);
    if (pending) {
        xSemaphoreGive(mutex);
        return ESP_ERR_INVALID_STATE;
    }
    cJSON *copy = cJSON_Duplicate(o, true);
    if (!copy) {
        xSemaphoreGive(mutex);
        return ESP_ERR_NO_MEM;
    }
    pending = true;
    xSemaphoreGive(mutex);
    if (xQueueSend(commands, &copy, 0) != pdTRUE) {
        cJSON_Delete(copy);
        xSemaphoreTake(mutex, portMAX_DELAY);
        pending = false;
        xSemaphoreGive(mutex);
        return ESP_FAIL;
    }
    return ESP_OK;
}
cJSON *ph_vpn_manager_status(void) {
    cJSON *o = cJSON_CreateObject();
    if (!o)
        return NULL;
    xSemaphoreTake(mutex, portMAX_DELAY);
    cJSON_AddStringToObject(o, "provider", cfg.provider);
    cJSON_AddStringToObject(o, "exit_ip", exit_ip);
    cJSON_AddStringToObject(o, "exit_country", exit_country);
    cJSON_AddNumberToObject(o, "exit_checked_ago_seconds",
                            exit_checked ? (esp_timer_get_time() - exit_checked) / 1000000 : -1);
    cJSON_AddStringToObject(o, "state", state);
    cJSON_AddStringToObject(o, "error", error);
    cJSON_AddBoolToObject(o, "enabled", cfg.enabled);
    cJSON_AddBoolToObject(o, "busy", pending);
    cJSON_AddBoolToObject(o, "api_verified", api_verified);
    cJSON_AddBoolToObject(o, "account_configured", *cfg.nord_key != 0);
    cJSON_AddStringToObject(o, "country", cfg.country);
    cJSON_AddBoolToObject(o, "rotation", cfg.rotation);
    cJSON_AddBoolToObject(o, "exclude_restricted", cfg.exclude_restricted);
    cJSON_AddNumberToObject(o, "interval", cfg.interval);
    cJSON_AddStringToObject(o, "server", server_name);
    cJSON_AddStringToObject(o, "server_country", server_country);
    int64_t remaining = next_rotation ? (next_rotation - esp_timer_get_time()) / 1000000 : 0;
    cJSON_AddNumberToObject(o, "next_rotation_seconds", remaining > 0 ? remaining : 0);
    cJSON_AddStringToObject(o, "endpoint",
                            !strcmp(cfg.provider, "wireguard") ? cfg.profile.endpoint : "");
    xSemaphoreGive(mutex);
    return o;
}
