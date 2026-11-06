idf_component_register(SRCS "main.c" "gateway.c" "admin.c" "admin_serial.c" "vpn.c" "vpn_manager.c" "vpn_history.c" "wifi_probe.c" "wifi_manager.c" INCLUDE_DIRS "." PRIV_REQUIRES esp_eth esp_netif esp_event nvs_flash esp_timer esp_app_format app_update phoenix_core espressif__esp_tinyusb lwip esp_http_server esp_http_client mbedtls json wireguard bootloader_support esp_driver_uart esp_wifi espressif__esp_hosted EMBED_FILES "web/index.html" "web/app.css" "web/app.js" "web/countries.json")

if(CONFIG_PHOENIX_GATEWAY_BENCH)
 target_sources(${COMPONENT_LIB} PRIVATE "../benchmarks/gateway/startup.c")
 target_include_directories(${COMPONENT_LIB} PRIVATE "../results/gatewaybench")
endif()
