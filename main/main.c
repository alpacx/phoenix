#include "esp_eth.h"
#include "gateway.h"
#include "admin.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_chip_info.h"
#include "esp_ota_ops.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static const char *TAG="phoenix";
static void event(void *arg,esp_event_base_t base,int32_t id,void *data){
 if(base==ETH_EVENT){ESP_LOGI(TAG,"Ethernet event %ld",(long)id);if(id==ETHERNET_EVENT_START)ph_gateway_guard_eth();if(id==ETHERNET_EVENT_DISCONNECTED||id==ETHERNET_EVENT_STOP)ph_gateway_uplink(false);}
 if(base==IP_EVENT&&id==IP_EVENT_ETH_GOT_IP){ph_gateway_uplink(true);ip_event_got_ip_t *e=data;ESP_LOGI(TAG,"Ethernet DHCP " IPSTR,IP2STR(&e->ip_info.ip));}
}
void app_main(void){
 esp_chip_info_t chip;esp_chip_info(&chip);ESP_LOGI(TAG,"P4 revision %d; gateway disabled until provisioned",chip.revision);
 ESP_ERROR_CHECK(nvs_flash_init()); /* Never silently erase user secrets on NVS errors. */
 ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());
 eth_mac_config_t mc=ETH_MAC_DEFAULT_CONFIG();
 eth_esp32_emac_config_t ec=ETH_ESP32_EMAC_DEFAULT_CONFIG();
 ec.smi_gpio.mdc_num=31;ec.smi_gpio.mdio_num=52;
 ec.clock_config.rmii.clock_mode=EMAC_CLK_EXT_IN;ec.clock_config.rmii.clock_gpio=50;
 ec.emac_dataif_gpio.rmii=(eth_mac_rmii_gpio_config_t){.tx_en_num=49,.txd0_num=34,.txd1_num=35,.crs_dv_num=28,.rxd0_num=29,.rxd1_num=30};
 eth_phy_config_t pc=ETH_PHY_DEFAULT_CONFIG();pc.phy_addr=-1;pc.reset_gpio_num=51;
 esp_eth_mac_t *mac=esp_eth_mac_new_esp32(&ec,&mc);esp_eth_phy_t *phy=esp_eth_phy_new_ip101(&pc);
 ESP_ERROR_CHECK(mac&&phy?ESP_OK:ESP_ERR_NO_MEM);
 esp_eth_config_t config=ETH_DEFAULT_CONFIG(mac,phy);esp_eth_handle_t eth;
 ESP_ERROR_CHECK(esp_eth_driver_install(&config,&eth));
 esp_netif_config_t nc=ESP_NETIF_DEFAULT_ETH();esp_netif_t *net=esp_netif_new(&nc);ESP_ERROR_CHECK(net?ESP_OK:ESP_ERR_NO_MEM);
 ESP_ERROR_CHECK(esp_netif_attach(net,esp_eth_new_netif_glue(eth)));ph_eth=net;ph_gateway_start();ph_admin_start();
 ESP_ERROR_CHECK(esp_event_handler_register(ETH_EVENT,ESP_EVENT_ANY_ID,event,NULL));
 ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,IP_EVENT_ETH_GOT_IP,event,NULL));
 ESP_ERROR_CHECK(esp_eth_start(eth));
 for(;;){ESP_LOGI(TAG,"free heap=%lu",(unsigned long)esp_get_free_heap_size());vTaskDelay(pdMS_TO_TICKS(30000));}
}
