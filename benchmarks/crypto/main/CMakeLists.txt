set(crypto "${CMAKE_CURRENT_LIST_DIR}/../../../components/wireguard/src/crypto/refc")
idf_component_register(SRCS "benchmark.c" "${crypto}/../../crypto.c" "${crypto}/chacha20poly1305.c" "${crypto}/chacha20.c" "${crypto}/poly1305-donna.c" INCLUDE_DIRS "${crypto}" PRIV_REQUIRES esp_timer esp_system esphome__libsodium)
