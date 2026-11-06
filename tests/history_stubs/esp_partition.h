#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_PARTITION_TYPE_DATA 1
#define ESP_PARTITION_SUBTYPE_ANY 255
typedef struct {size_t size;} esp_partition_t;
const esp_partition_t *esp_partition_find_first(int,int,const char*);
int esp_partition_read(const esp_partition_t*,size_t,void*,size_t);
int esp_partition_write(const esp_partition_t*,size_t,const void*,size_t);
int esp_partition_erase_range(const esp_partition_t*,size_t,size_t);
