idf_component_register(SRCS "main.c" "gateway.c" "admin.c" "admin_serial.c" "vpn.c" "vpn_manager.c" "vpn_history.c" "wifi_probe.c" "wifi_manager.c" INCLUDE_DIRS "." PRIV_REQUIRES esp_eth esp_netif esp_event nvs_flash esp_timer esp_app_format app_update phoenix_core espressif__esp_tinyusb lwip esp_http_server esp_http_client mbedtls json wireguard bootloader_support esp_driver_uart esp_wifi espressif__esp_hosted EMBED_FILES "${CMAKE_CURRENT_LIST_DIR}/../../../shared/web/index.html" "${CMAKE_CURRENT_LIST_DIR}/../../../shared/web/app.css" "${CMAKE_CURRENT_LIST_DIR}/../../../shared/web/app.js" "${CMAKE_CURRENT_LIST_DIR}/../../../shared/web/countries.json")

if(CONFIG_PHOENIX_GATEWAY_BENCH)
 target_sources(${COMPONENT_LIB} PRIVATE "${CMAKE_CURRENT_LIST_DIR}/../../../benchmarks/gateway/startup.c")
 target_include_directories(${COMPONENT_LIB} PRIVATE "${CMAKE_CURRENT_LIST_DIR}/../../../results/gatewaybench")
endif()
