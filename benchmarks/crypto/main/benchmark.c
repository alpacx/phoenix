#include <string.h>
#include <assert.h>
#include "chacha20poly1305.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static uint8_t plain[1424], encrypted[1440], decoded[1424];
/* Public synthetic key; never used for network traffic. */
static const uint8_t key[32] = {1, 2, 3, 4};
void app_main(void) {
    const size_t sizes[] = {64, 512, 1424};
    ESP_LOGI("bench", "LOCAL CRYPTO ONLY; no USB/network; single task; performance build");
    for (size_t i = 0; i < sizeof(plain); ++i) plain[i] = (uint8_t)i;
    for (unsigned s = 0; s < 3; ++s) {
        size_t len = sizes[s];
        for (unsigned trial = 0; trial < 3; ++trial) {
            int64_t enc_us = 0, dec_us = 0;
            const unsigned count = 1000;
            for (unsigned n = 0; n < count; ++n) {
                uint64_t nonce = ((uint64_t)s * 3 + trial) * count + n;
                int64_t t = esp_timer_get_time();
                chacha20poly1305_encrypt(encrypted, plain, len, NULL, 0, nonce, key);
                enc_us += esp_timer_get_time() - t;
                t = esp_timer_get_time();
                bool ok = chacha20poly1305_decrypt(decoded, encrypted, len + 16, NULL, 0, nonce, key);
                dec_us += esp_timer_get_time() - t;
                assert(ok && memcmp(plain, decoded, len) == 0);
                if (n % 32 == 0) vTaskDelay(1);
            }
            encrypted[len] ^= 1;
            assert(!chacha20poly1305_decrypt(decoded, encrypted, len + 16, NULL, 0,
                    ((uint64_t)s * 3 + trial) * count + count - 1, key));
            ESP_LOGI("bench", "bytes=%u trial=%u packets=%u encrypt_us=%lld decrypt_us=%lld encrypt_Mbps=%.2f decrypt_Mbps=%.2f heap=%lu",
                (unsigned)len, trial + 1, count, (long long)enc_us, (long long)dec_us,
                (double)len * 8 * count / enc_us, (double)len * 8 * count / dec_us,
                (unsigned long)esp_get_free_heap_size());
        }
    }
    ESP_LOGI("bench", "DONE: roundtrip and tampered-tag checks passed; timings exclude yields and verification");
}
