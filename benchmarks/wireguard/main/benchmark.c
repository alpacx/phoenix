#include <errno.h>
#include <sys/time.h>
#include "esp_netif.h"
#include "esp_netif_net_stack.h"
#include "lwip/tcpip.h"
#include "lwip/ip.h"
#include "wireguard-platform.h"
#include "wireguardif.h"
#include "bench_keys.h"
#include <string.h>
#include <unistd.h>
#include "esp_eth.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "lwip/sockets.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static const char *TAG = "wgbench";
static uint8_t buffer[8192];
static void server(void *arg) {
    int listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    ESP_ERROR_CHECK(listener < 0 ? ESP_FAIL : ESP_OK);
    struct sockaddr_in addr = {.sin_family=AF_INET, .sin_port=htons(5001), .sin_addr.s_addr=inet_addr("10.77.0.2")};
    ESP_ERROR_CHECK(bind(listener, (struct sockaddr *)&addr, sizeof(addr)) ? ESP_FAIL : ESP_OK);
    ESP_ERROR_CHECK(listen(listener, 1) ? ESP_FAIL : ESP_OK);
    ESP_LOGI(TAG, "TCP benchmark port 5001; U=receive D=send; 32 MiB per run");
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        if (fd < 0) {vTaskDelay(pdMS_TO_TICKS(100)); continue;}
        struct timeval timeout = {.tv_sec=10};
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
        char command;
        if (recv(fd, &command, 1, 0) != 1 || (command != 'U' && command != 'D')) {close(fd); continue;}
        unsigned total = 0, target = 32 * 1024 * 1024;
        int64_t start = esp_timer_get_time();
        while (total < target && esp_timer_get_time() - start < 120000000) {
            size_t len = target-total < sizeof(buffer) ? target-total : sizeof(buffer);
            int n = command == 'U' ? recv(fd, buffer, len, 0) : send(fd, buffer, len, 0);
            if (n <= 0) break;
            total += n;
        }
        int64_t elapsed = esp_timer_get_time()-start;
        if (command == 'U') { uint32_t ack=htonl(total); send(fd, &ack, sizeof(ack), 0); }
        ESP_LOGI(TAG, "direction=%c bytes=%u elapsed_us=%lld Mbps=%.2f complete=%d heap=%lu", command,total,(long long)elapsed,total*8.0/elapsed,total==target,(unsigned long)esp_get_free_heap_size());
        shutdown(fd, SHUT_RDWR); close(fd);
    }
}
static struct netif tunnel;
static esp_netif_t *uplink;
static uint8_t peer_id;
static bool started;
static void start_tunnel(void *unused) {
    if (started) return;
    struct timeval tv = {.tv_sec=BENCH_EPOCH};
    settimeofday(&tv, NULL);
    ESP_ERROR_CHECK(wireguard_platform_init());
    ip4_addr_t addr, mask, gateway;
    ip4addr_aton("10.77.0.2", &addr);
    ip4addr_aton("255.255.255.0", &mask);
    ip4_addr_set_zero(&gateway);
    struct wireguardif_init_data init = {.private_key=BENCH_P4_PRIVATE,
        .listen_port=51820, .bind_netif=esp_netif_get_netif_impl(uplink)};
    ESP_ERROR_CHECK(netif_add(&tunnel,&addr,&mask,&gateway,&init,wireguardif_init,ip_input) ? ESP_OK : ESP_FAIL);
    tunnel.mtu=1420;
    netif_set_up(&tunnel);
    struct wireguardif_peer peer;
    wireguardif_peer_init(&peer);
    peer.public_key=BENCH_HOST_PUBLIC;
    ipaddr_aton("10.77.0.1", &peer.allowed_ip);
    ipaddr_aton("255.255.255.255", &peer.allowed_mask);
    ipaddr_aton(BENCH_HOST_IP, &peer.endpoint_ip);
    peer.endport_port=51821;
    peer.keep_alive=5;
    ESP_ERROR_CHECK(wireguardif_add_peer(&tunnel,&peer,&peer_id)==ERR_OK ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(wireguardif_connect(&tunnel,peer_id)==ERR_OK ? ESP_OK : ESP_FAIL);
    started=true;
    ESP_LOGI(TAG,"WireGuard configured: 10.77.0.2 MTU=1420; waiting handshake");
    ESP_ERROR_CHECK(xTaskCreate(server,"tcp_bench",4096,NULL,5,NULL)==pdPASS ? ESP_OK : ESP_FAIL);
}
static void event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base==ETH_EVENT) {
        ESP_LOGI(TAG, "Ethernet event=%ld", (long)id);
        if (id==ETHERNET_EVENT_CONNECTED) {
            esp_eth_handle_t eth=*(esp_eth_handle_t *)data;
            eth_speed_t speed; eth_duplex_t duplex;
            ESP_ERROR_CHECK(esp_eth_ioctl(eth, ETH_CMD_G_SPEED, &speed));
            ESP_ERROR_CHECK(esp_eth_ioctl(eth, ETH_CMD_G_DUPLEX_MODE, &duplex));
            ESP_LOGI(TAG, "link speed=%d Mbps duplex=%s", speed==ETH_SPEED_100M?100:10,duplex==ETH_DUPLEX_FULL?"full":"half");
        }
    }
    if (base==IP_EVENT && id==IP_EVENT_ETH_GOT_IP) {
        ip_event_got_ip_t *e=data;
        ESP_LOGI(TAG, "DHCP " IPSTR, IP2STR(&e->ip_info.ip));
        ESP_ERROR_CHECK(tcpip_callback(start_tunnel,NULL)==ERR_OK ? ESP_OK : ESP_FAIL);
    }
}
void app_main(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    eth_mac_config_t mc = ETH_MAC_DEFAULT_CONFIG();
    eth_esp32_emac_config_t ec = ETH_ESP32_EMAC_DEFAULT_CONFIG();
    ec.smi_gpio.mdc_num = 31;
    ec.smi_gpio.mdio_num = 52;
    ec.clock_config.rmii.clock_mode = EMAC_CLK_EXT_IN;
    ec.clock_config.rmii.clock_gpio = 50;
    ec.emac_dataif_gpio.rmii = (eth_mac_rmii_gpio_config_t){.tx_en_num = 49,
                                                            .txd0_num = 34,
                                                            .txd1_num = 35,
                                                            .crs_dv_num = 28,
                                                            .rxd0_num = 29,
                                                            .rxd1_num = 30};
    eth_phy_config_t pc = ETH_PHY_DEFAULT_CONFIG();
    pc.phy_addr = -1;
    pc.reset_gpio_num = 51;
    esp_eth_mac_t *mac = esp_eth_mac_new_esp32(&ec, &mc);
    esp_eth_phy_t *phy = esp_eth_phy_new_ip101(&pc);
    ESP_ERROR_CHECK(mac && phy ? ESP_OK : ESP_ERR_NO_MEM);
    esp_eth_config_t config = ETH_DEFAULT_CONFIG(mac, phy);
    esp_eth_handle_t eth;
    ESP_ERROR_CHECK(esp_eth_driver_install(&config, &eth));
    esp_netif_config_t nc = ESP_NETIF_DEFAULT_ETH();
    esp_netif_t *net = esp_netif_new(&nc);
    ESP_ERROR_CHECK(net ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(esp_netif_attach(net, esp_eth_new_netif_glue(eth)));
    ESP_ERROR_CHECK(esp_event_handler_register(ETH_EVENT, ESP_EVENT_ANY_ID, event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_ETH_GOT_IP, event, NULL));
    uplink=net;
    ESP_ERROR_CHECK(esp_eth_start(eth));

}
