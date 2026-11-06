/* Append-only, CRC-protected flash journal. A sector is erased only when reused.
 * No keys or credentials. Entries expire after eight hours. */
#include "vpn_history.h"
#include "esp_crc.h"
#include "esp_partition.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
#define SECTOR 4096
#define PER_SECTOR 42
#define CAPACITY (32 * PER_SECTOR)
#define MAGIC 0x50484831u
#define WINDOW (8 * 3600)
typedef struct {
    uint32_t magic, sequence, timestamp, server_id;
    char country[4], server[64];
    uint8_t reserved[8];
    uint32_t crc;
} entry;
_Static_assert(sizeof(entry) == 96, "journal record size");
static entry records[CAPACITY];
static const esp_partition_t *partition;
static SemaphoreHandle_t lock;
static uint32_t sequence;
static unsigned next_slot;
static bool storage_ok;
static size_t offset(unsigned slot) {
    return (slot / PER_SECTOR) * SECTOR + (slot % PER_SECTOR) * sizeof(entry);
}
static bool valid(const entry *e) {
    return e->magic == MAGIC && e->sequence && e->country[2] == 0 && e->server[63] == 0 &&
           e->crc == esp_crc32_le(0, (const uint8_t *)e, sizeof(entry) - 4);
}
void ph_history_init(void) {
    lock = xSemaphoreCreateMutex();
    configASSERT(lock);
    partition =
        esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, "vpn_history");
    if (!partition || partition->size < 32 * SECTOR)
        return;
    storage_ok = true;
    for (unsigned i = 0; i < CAPACITY; i++) {
        entry e;
        if (esp_partition_read(partition, offset(i), &e, sizeof e) != ESP_OK) {
            storage_ok = false;
            continue;
        }
        if (valid(&e)) {
            records[i] = e;
            if (e.sequence > sequence) {
                sequence = e.sequence;
                next_slot = (i + 1) % CAPACITY;
            }
        }
    }
}
void ph_history_add(const char *country, const char *server, uint32_t id) {
    if (!lock)
        return;
    xSemaphoreTake(lock, portMAX_DELAY);
    entry e = {
        .magic = MAGIC, .sequence = ++sequence, .timestamp = (uint32_t)time(NULL), .server_id = id};
    snprintf(e.country, sizeof e.country, "%.2s", country);
    snprintf(e.server, sizeof e.server, "%s", server);
    e.crc = esp_crc32_le(0, (const uint8_t *)&e, sizeof(e) - 4);
    if (partition) {
        /* Skip a partially written slot after power loss; reuse its next sector. */
        entry old;
        if (next_slot % PER_SECTOR &&
            (esp_partition_read(partition, offset(next_slot), &old, sizeof old) != ESP_OK ||
             old.magic != UINT32_MAX))
            next_slot = ((next_slot / PER_SECTOR + 1) * PER_SECTOR) % CAPACITY;
        esp_err_t err = ESP_OK;
        if (next_slot % PER_SECTOR == 0) {
            err = esp_partition_erase_range(partition, offset(next_slot), SECTOR);
            memset(records + next_slot, 0, PER_SECTOR * sizeof(entry));
        }
        if (err == ESP_OK)
            err = esp_partition_write(partition, offset(next_slot), &e, sizeof e);
        storage_ok = err == ESP_OK;
    }
    records[next_slot] = e;
    next_slot = (next_slot + 1) % CAPACITY;
    xSemaphoreGive(lock);
}
cJSON *ph_history_page(uint32_t before) {
    cJSON *o = cJSON_CreateObject(), *a = cJSON_AddArrayToObject(o, "entries");
    uint32_t now = (uint32_t)time(NULL), cursor = before ? before : UINT32_MAX, last = 0;
    unsigned count = 0;
    bool more = false;
    xSemaphoreTake(lock, portMAX_DELAY);
    while (count < 33) {
        const entry *best = NULL;
        for (unsigned i = 0; i < CAPACITY; i++) {
            const entry *e = &records[i];
            if (e->magic == MAGIC && e->sequence < cursor && e->timestamp <= now &&
                now - e->timestamp < WINDOW && (!best || e->sequence > best->sequence))
                best = e;
        }
        if (!best)
            break;
        if (count == 32) {
            more = true;
            break;
        }
        cJSON *v = cJSON_CreateObject();
        cJSON_AddNumberToObject(v, "id", best->sequence);
        cJSON_AddNumberToObject(v, "connected_at", best->timestamp);
        cJSON_AddStringToObject(v, "country", best->country);
        cJSON_AddStringToObject(v, "server", best->server);
        cJSON_AddItemToArray(a, v);
        cursor = last = best->sequence;
        count++;
    }
    cJSON_AddBoolToObject(o, "persistent", storage_ok);
    xSemaphoreGive(lock);
    cJSON_AddNumberToObject(o, "next_before", more ? last : 0);
    cJSON_AddNumberToObject(o, "window_seconds", WINDOW);
    cJSON_AddNumberToObject(o, "now", now);
    return o;
}
