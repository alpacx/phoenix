#pragma once
#include "esp_err.h"
#include "esp_wifi.h"
void ph_wifi_setup(void);
esp_err_t ph_wifi_initialize(void);
esp_err_t ph_wifi_scan(wifi_ap_record_t *records, uint16_t *count);
esp_err_t ph_wifi_configure(bool ap, const char *ssid, const char *password, bool save, bool saved);
