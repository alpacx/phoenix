#include "admin.h"
#include "esp_chip_info.h"
#include "esp_eth.h"
#include "esp_event.h"
#include "esp_image_format.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_ota_ops.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "gateway.h"
#include "nvs_flash.h"
#include "wifi_manager.h"
void ph_wifi_probe_start(void);
static const char *TAG = "phoenix";
static void event(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == ETH_EVENT) {
        ESP_LOGI(TAG, "Ethernet event %ld", (long)id);
        if (id == ETHERNET_EVENT_START) {
            ph_gateway_guard_eth();
            esp_ota_img_states_t state;
            const esp_partition_t *running = esp_ota_get_running_partition();
            if (esp_ota_get_state_partition(running, &state) == ESP_OK &&
                state == ESP_OTA_IMG_PENDING_VERIFY) {
                esp_err_t e = esp_ota_mark_app_valid_cancel_rollback();
                ESP_LOGI(TAG, "boot health confirmation: %s", esp_err_to_name(e));
            }
        }
        if (id == ETHERNET_EVENT_DISCONNECTED || id == ETHERNET_EVENT_STOP)
            ph_gateway_uplink(false);
    }
    if (base == IP_EVENT && id == IP_EVENT_ETH_GOT_IP) {
        ip_event_got_ip_t *e = data;
        uint32_t mask = e->ip_info.netmask.addr;
        esp_ip4_addr_t usb, ap;
        esp_netif_str_to_ip4("192.168.7.1", &usb);
        esp_netif_str_to_ip4("192.168.8.1", &ap);
        bool overlap = (e->ip_info.ip.addr & mask) == (usb.addr & mask) ||
                       (e->ip_info.ip.addr & mask) == (ap.addr & mask);
        ph_gateway_uplink(!overlap);
        if (overlap)
            ESP_LOGE(TAG, "uplink overlaps a client subnet; forwarding blocked");
        ESP_LOGI(TAG, "Ethernet DHCP " IPSTR, IP2STR(&e->ip_info.ip));
    }
    if (base == IP_EVENT && id == IP_EVENT_ETH_LOST_IP)
        ph_gateway_uplink(false);
}
void app_main(void) {
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    ESP_LOGI(TAG, "P4 revision %d; gateway disabled until provisioned", chip.revision);
#if CONFIG_SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT
    const esp_partition_t *running = esp_ota_get_running_partition();
    const esp_partition_pos_t position = {.offset = running->address, .size = running->size};
    esp_image_metadata_t metadata;
    ESP_ERROR_CHECK(esp_image_verify(ESP_IMAGE_VERIFY, &position, &metadata));
    ESP_LOGI(TAG, "running app software signature verified");
#endif
    ESP_ERROR_CHECK(nvs_flash_init()); /* Never silently erase user secrets on NVS errors. */
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
    ph_eth = net;
    ph_gateway_start();
    ph_wifi_setup();
    ph_admin_start();
    ESP_ERROR_CHECK(esp_event_handler_register(ETH_EVENT, ESP_EVENT_ANY_ID, event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, ESP_EVENT_ANY_ID, event, NULL));
    ESP_ERROR_CHECK(esp_eth_start(eth));
    ph_wifi_probe_start();
    for (;;) {
        ESP_LOGI(TAG, "free heap=%lu", (unsigned long)esp_get_free_heap_size());
        vTaskDelay(pdMS_TO_TICKS(30000));
    }
}
