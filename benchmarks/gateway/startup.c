/* Explicit bench build only: production packet path, isolated test credentials. */
#include "admin.h"
#include "bench_keys.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_net_stack.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gateway.h"
#include "lwip/inet_chksum.h"
#include "lwip/ip4.h"
#include "lwip/pbuf.h"
#include "lwip/tcpip.h"
#include "vpn.h"
#include "vpn_manager.h"
#include "wifi_manager.h"
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

static bool start_vpn(void) {
    ph_wg_profile p = {.private_key = BENCH_P4_PRIVATE,
                       .public_key = BENCH_HOST_PUBLIC,
                       .address = "10.77.0.2",
                       .prefix = 24,
                       .endpoint = BENCH_HOST_IP,
                       .port = 51821,
                       .keepalive = 5,
                       .mtu = 1420};
    strcpy(p.dns, "1.1.1.1");
    ph_vpn_manager_bench(&p);
    return true;
}
/* Synthetic client ingress exercises the actual IP firewall/route/NAPT/egress.
 * The positive control in direct mode must be seen by the Mac capture. */
static void probe(void *unused) {
    struct netif *ap = esp_netif_get_netif_impl(ph_ap);
    ip4_addr_t dst;
    ip4addr_aton(BENCH_HOST_IP, &dst);
    for (unsigned i = 0; i < 3; i++) {
        uint8_t b[40] = {0x45, 0, 0, 40, 0xfa, 0, 0, 0, 64, 17};
        b[5] = i;
        b[12] = 192;
        b[13] = 168;
        b[14] = 9;
        b[15] = 250;
        memcpy(b + 16, &dst.addr, 4);
        b[20] = 0xd6;
        b[21] = 0xd8 + i; /* unique source port */
        unsigned port = i == 0 ? 53 : (i == 1 ? 8081 : 443);
        b[22] = port >> 8;
        b[23] = port;
        b[24] = 0;
        b[25] = 20;
        memcpy(b + 28, "PHOENIXPROBE", 12);
        uint16_t sum = inet_chksum(b, 20);
        memcpy(b + 10, &sum, 2);
        struct pbuf *p = pbuf_alloc(PBUF_LINK, sizeof b, PBUF_RAM);
        if (p) {
            pbuf_take(p, b, sizeof b);
            ip4_input(p, ap);
        }
    }
    ESP_LOGI("gatewaybench", "probe injected: 3 UDP packets from simulated AP client to Mac, ports "
                             "53/8081/443 IDs 64000..64002");
}

static void run(void *unused) {
    ESP_ERROR_CHECK(ph_wifi_configure(true, "Phoenix-Test", BENCH_AP_PASSWORD, false, false));
    ESP_LOGI("gatewaybench", "AP Phoenix-Test at 192.168.9.1; USB off; direct mode off");
    ph_firewall f;
    do {
        vTaskDelay(pdMS_TO_TICKS(1000));
        ph_gateway_snapshot(&f);
    } while (!f.uplink_ready);

    ESP_ERROR_CHECK(start_vpn() ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(uart_driver_install(CONFIG_ESP_CONSOLE_UART_NUM, 1024, 0, 0, NULL, 0));
    char *line = calloc(1, 16385);
    configASSERT(line);
    unsigned len = 0;
    bool overflow = false;
    int64_t next = 0;
    int64_t direct_until = 0;
    for (;;) {
        uint8_t byte;
        if (uart_read_bytes(CONFIG_ESP_CONSOLE_UART_NUM, &byte, 1, pdMS_TO_TICKS(100)) == 1) {
            if (byte == '\n') {
                line[len] = 0;
                if (overflow) {
                } else if (!strncmp(line, "admin ", 6))
                    ph_admin_serial(line + 6);
                else if (!strcmp(line, "bench status")) {
                    cJSON *o = ph_vpn_manager_status();
                    char *t = cJSON_PrintUnformatted(o);
                    if (t) {
                        printf("PHSTATUS %s\n", t);
                        fflush(stdout);
                        free(t);
                    }
                    cJSON_Delete(o);
                } else if (!strncmp(line, "pair ", 5))
                    ph_admin_pair(line + 5);
                else if (!strcmp(line, "bench blocked")) {
                    ph_gateway_direct(false);
                    direct_until = 0;
                    ESP_LOGI("gatewaybench", "MODE blocked");
                } else if (!strcmp(line, "bench direct")) {
                    ph_gateway_direct(true);
                    direct_until = esp_timer_get_time() + 300000000;
                    ESP_LOGW("gatewaybench", "MODE direct, automatic VPN restore in 300 seconds");
                } else if (!strcmp(line, "bench vpn")) {
                    ph_gateway_direct(false);
                    direct_until = 0;
                    ESP_ERROR_CHECK(start_vpn() ? ESP_OK : ESP_FAIL);
                    ESP_LOGI("gatewaybench", "MODE vpn");
                } else if (!strcmp(line, "bench probe")) {
                    ESP_ERROR_CHECK(tcpip_callback(probe, NULL) == ERR_OK ? ESP_OK : ESP_FAIL);
                }
                memset(line, 0, 16385);
                len = 0;
                overflow = false;
            } else if (len < 16384)
                line[len++] = byte;
            else
                overflow = true;
        }
        if (direct_until && esp_timer_get_time() > direct_until) {
            ph_gateway_direct(false);
            direct_until = 0;
            ESP_ERROR_CHECK(start_vpn() ? ESP_OK : ESP_FAIL);
            ESP_LOGI("gatewaybench", "MODE vpn (direct timeout)");
        }
        if (esp_timer_get_time() < next)
            continue;
        next = esp_timer_get_time() + 5000000;
        ph_gateway_snapshot(&f);
        ESP_LOGI("gatewaybench",
                 "uplink=%d vpn=%d direct=%d allowed=%llu blocked=%llu malformed=%llu heap=%lu",
                 f.uplink_ready, f.tunnel_ready, f.direct_enabled, (unsigned long long)f.allowed,
                 (unsigned long long)f.blocked, (unsigned long long)f.malformed,
                 (unsigned long)esp_get_free_heap_size());
    }
}
void ph_gateway_bench_start(void) {
    configASSERT(xTaskCreate(run, "gatewaybench", 8192, NULL, 3, NULL) == pdPASS);
}
