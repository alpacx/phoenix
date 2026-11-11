#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "wifi_manager.h"
#if CONFIG_PHOENIX_C6_PROBE
static void probe(void *arg) {
    wifi_ap_record_t records[16];
    uint16_t count = 16;
    esp_err_t e = ph_wifi_scan(records, &count);
    if (e == ESP_OK)
        ESP_LOGI("c6_probe", "scan completed: %u networks (capped at 16); no connection attempted",
                 count);
    ESP_LOGI("c6_probe", "probe result: %s", esp_err_to_name(e));
    vTaskDelete(NULL);
}
#endif
void ph_wifi_probe_start(void) {
#if CONFIG_PHOENIX_C6_PROBE
    if (xTaskCreate(probe, "c6_probe", 8192, NULL, 3, NULL) != pdPASS)
        ESP_LOGE("c6_probe", "task allocation failed");
#endif
}
