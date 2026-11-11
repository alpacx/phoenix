/* Authenticated serial transport for the SAME HTTP handlers. This is an admin
 * channel, not a USB network adapter. No credentials are printed back. */
#include "admin.h"
#include "cJSON.h"
#include "lwip/sockets.h"
#include "mbedtls/platform_util.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static const char *value(const cJSON *o, const char *k) {
    cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    return cJSON_IsString(v) ? v->valuestring : "";
}
void ph_admin_serial(const char *line) {
    cJSON *o = cJSON_ParseWithOpts(line, NULL, true);
    cJSON *id = cJSON_GetObjectItemCaseSensitive(o, "id");
    if (!cJSON_IsNumber(id) || id->valuedouble < 0 || id->valuedouble > 2147483647) {
        cJSON_Delete(o);
        return;
    }
    int request_id = id->valueint, code = 400, fd = -1;
    char *body = NULL, *response = NULL;
    cJSON *result = NULL;
    const char *method = value(o, "method"), *path = value(o, "path"), *token = value(o, "token");
    bool route = !strcmp(path, "vpn/history") || !strncmp(path, "vpn/history?before=", 19) ||
                 !strcmp(path, "status") || !strcmp(path, "policy") || !strcmp(path, "vpn") ||
                 !strcmp(path, "mode") || !strcmp(path, "uplink") || !strcmp(path, "wifi");
    bool valid =
        route && (!strcmp(method, "GET") || !strcmp(method, "POST")) && strlen(token) == 64;
    for (unsigned i = 0; valid && i < 64; i++)
        if (!strchr("0123456789abcdef", token[i]))
            valid = false;
    if (!valid)
        goto done;
    cJSON *payload = cJSON_GetObjectItemCaseSensitive(o, "body");
    body = payload ? cJSON_PrintUnformatted(payload) : strdup("");
    if (!body)
        goto done;
    fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (fd < 0)
        goto done;
    struct timeval timeout = {.tv_sec = 5};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
    struct sockaddr_in addr = {
        .sin_family = AF_INET, .sin_port = htons(80), .sin_addr.s_addr = htonl(0x7f000001)};
    if (connect(fd, (struct sockaddr *)&addr, sizeof addr) != 0)
        goto done;
    size_t cap = strlen(body) + 512;
    char *request = calloc(1, cap);
    if (!request)
        goto done;
    int n = snprintf(
        request, cap,
        "%s /api/v1/%s HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer %s\r\nContent-Type: "
        "application/json\r\nContent-Length: %u\r\nConnection: close\r\n\r\n%s",
        method, path, token, (unsigned)strlen(body), body);
    int sent = 0;
    while (sent < n) {
        int w = send(fd, request + sent, n - sent, 0);
        if (w <= 0)
            break;
        sent += w;
    }
    mbedtls_platform_zeroize(request, cap);
    free(request);
    if (sent != n)
        goto done;
    response = calloc(1, 16385);
    if (!response)
        goto done;
    size_t have = 0;
    code = 502;
    while (have < 16384) {
        int r = recv(fd, response + have, 16384 - have, 0);
        if (r <= 0)
            break;
        have += r;
        response[have] = 0;
        char *start = strstr(response, "\r\n\r\n");
        if (start) {
            result = cJSON_ParseWithOpts(start + 4, NULL, true);
            if (result) {
                sscanf(response, "HTTP/%*s %d", &code);
                break;
            }
        }
    }
done:
    if (fd >= 0)
        close(fd);
    if (!result) {
        result = cJSON_CreateObject();
        cJSON_AddStringToObject(result, "error", "serial_request_failed");
    }
    cJSON *envelope = cJSON_CreateObject();
    cJSON_AddNumberToObject(envelope, "id", request_id);
    cJSON_AddNumberToObject(envelope, "status", code);
    cJSON_AddItemToObject(envelope, "body", result);
    char *text = cJSON_PrintUnformatted(envelope);
    if (text) {
        printf("PHADMIN %s\n", text);
        fflush(stdout);
        free(text);
    }
    cJSON_Delete(envelope);
    if (body) {
        mbedtls_platform_zeroize(body, strlen(body));
        free(body);
    }
    if (response) {
        mbedtls_platform_zeroize(response, 16385);
        free(response);
    }
    cJSON *t = cJSON_GetObjectItemCaseSensitive(o, "token");
    if (cJSON_IsString(t))
        mbedtls_platform_zeroize(t->valuestring, strlen(t->valuestring));
    /* The original input line is also wiped by the UART owner after dispatch. */
    cJSON_Delete(o);
}
