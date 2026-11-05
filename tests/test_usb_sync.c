/* Deterministic scheduler tests compile the actual overridden sync functions. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;
typedef unsigned TickType_t;
typedef unsigned EventBits_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NO_MEM -2
#define ESP_ERR_INVALID_STATE -3
#define ESP_ERR_TIMEOUT -4
#define pdTRUE 1
#define portMAX_DELAY 0xffffffffU
#define ESP_RETURN_ON_FALSE(c, e, tag, msg) do { if (!(c)) return (e); } while (0)
typedef struct packet { void *buffer, *buff_free_arg; uint16_t len; esp_err_t result; } packet_t;
static struct { int *buffer_sema; unsigned *tx_flags; packet_t *packet_to_send; } s_net_obj;
static uintptr_t sync_generation;
static const unsigned TX_FINISHED_BIT = 1;
static int sem;
static unsigned flags, sends, queued;
static bool ready = true, accepts = true;
static enum { NORMAL, TIMEOUT_BEFORE, TIMEOUT_DURING } schedule;
static struct { void (*fn)(void *); void *arg; } queue[8];
static int *xSemaphoreCreateBinary(void) { sem = 0; return &sem; }
static unsigned *xEventGroupCreate(void) { flags = 0; return &flags; }
static int xSemaphoreTake(int *s, TickType_t timeout) {
    if (!*s) { assert(timeout != portMAX_DELAY); return 0; }
    *s = 0; return 1;
}
static void xSemaphoreGive(int *s) { assert(!*s); *s = 1; }
static void xEventGroupSetBits(unsigned *f, unsigned bits) { *f |= bits; }
static void xEventGroupClearBits(unsigned *f, unsigned bits) { *f &= ~bits; }
static bool tud_ready(void) { return ready; }
static bool tud_network_can_xmit(unsigned len) { assert(len == 4); return accepts; }
static void tud_network_xmit(void *ref, uint16_t len) {
    packet_t *p = ref;
    assert(len == 4 && p->len == 4 && !memcmp(p->buffer, "test", 4));
    sends++;
}
static void usbd_defer_func(void (*fn)(void *), void *arg, bool isr) {
    assert(!isr && queued < 8);
    queue[queued].fn = fn; queue[queued++].arg = arg;
}
static void dispatch(void) {
    for (unsigned i = 0; i < queued; i++) queue[i].fn(queue[i].arg);
    queued = 0;
}
static EventBits_t xEventGroupWaitBits(unsigned *f, unsigned bits, int clear, int all, TickType_t timeout) {
    assert(clear && all && timeout == 10);
    assert(!(*f & bits)); /* no stale completion from a previous timed-out send */
    if (schedule == TIMEOUT_BEFORE) return 0;
    dispatch();
    if (schedule == TIMEOUT_DURING) return 0;
    unsigned result = *f & bits;
    *f &= ~bits;
    return result;
}
#include "usb_sync_under_test.inc"
int main(void) {
    char buffer[] = "test";
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_OK && sends == 1);
    schedule = TIMEOUT_BEFORE;
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_ERR_TIMEOUT && sends == 1);
    /* Delayed callback from old transaction is queued ahead of the new one. */
    schedule = NORMAL;
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_OK && sends == 2);
    schedule = TIMEOUT_DURING;
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_ERR_TIMEOUT && sends == 3);
    schedule = NORMAL;
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_OK && sends == 4);
    accepts = false;
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_FAIL && sends == 4);
    ready = false;
    assert(tinyusb_net_send_sync(buffer, 4, NULL, 10) == ESP_ERR_INVALID_STATE);
    puts("USB sync: normal, timeout, late callback isolation, stale completion, backpressure PASS");
}
