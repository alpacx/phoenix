#include "vpn_history.h"
static esp_err_t history_get(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    char query[64], value[16];
    uint32_t before = 0;
    if (httpd_req_get_url_query_str(r, query, sizeof query) == ESP_OK &&
        httpd_query_key_value(query, "before", value, sizeof value) == ESP_OK) {
        char *end;
        unsigned long n = strtoul(value, &end, 10);
        if (!*value || *end || n > UINT32_MAX)
            return reply(r, "400 Bad Request", "{}");
        before = (uint32_t)n;
    }
    cJSON *o = ph_history_page(before);
    char *body = cJSON_PrintUnformatted(o);
    cJSON_Delete(o);
    if (!body)
        return ESP_ERR_NO_MEM;
    esp_err_t result = reply(r, "200 OK", body);
    free(body);
    return result;
}
/* Included by admin.c to share authentication and response helpers. */
static cJSON *request_json(httpd_req_t *r, size_t max) {
    if (!local_origin(r) || r->content_len < 2 || r->content_len > max)
        return NULL;
    char *body = calloc(1, r->content_len + 1);
    if (!body)
        return NULL;
    size_t have = 0;
    while (have < r->content_len) {
        int n = httpd_req_recv(r, body + have, r->content_len - have);
        if (n <= 0) {
            memset(body, 0, r->content_len);
            free(body);
            return NULL;
        }
        have += n;
    }
    cJSON *o = cJSON_ParseWithOpts(body, NULL, true);
    memset(body, 0, r->content_len);
    free(body);
    return o;
}
static esp_err_t json_reply(httpd_req_t *r, cJSON *o) {
    if (!o)
        return ESP_ERR_NO_MEM;
    char *b = cJSON_PrintUnformatted(o);
    cJSON_Delete(o);
    if (!b)
        return ESP_ERR_NO_MEM;
    esp_err_t e = reply(r, "200 OK", b);
    free(b);
    return e;
}
static bool json_int(const cJSON *o, const char *k, unsigned max, unsigned *out) {
    cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    if (!cJSON_IsNumber(v) || v->valuedouble < 0 || v->valuedouble > max ||
        v->valuedouble != (unsigned)v->valuedouble)
        return false;
    *out = (unsigned)v->valuedouble;
    return true;
}
static const char *json_string(const cJSON *o, const char *k) {
    cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}
static bool json_bool(const cJSON *o, const char *k, bool *out) {
    cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    if (!cJSON_IsBool(v))
        return false;
    *out = cJSON_IsTrue(v);
    return true;
}
static void add_cidr(cJSON *o, const char *k, uint32_t ip, uint32_t mask) {
    char text[24];
    ph_cidr_format(ip, mask, text, sizeof text);
    cJSON_AddStringToObject(o, k, text);
}
static bool get_cidr(const cJSON *o, const char *k, uint32_t *ip, uint32_t *mask) {
    return ph_cidr_parse(json_string(o, k), ip, mask);
}
static esp_err_t policy_get(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    ph_policy p;
    bool active[PH_PORT_FORWARDS];
    ph_gateway_policy_get(&p, active);
    cJSON *o = cJSON_CreateObject();
    cJSON_AddNumberToObject(o, "revision", p.revision);
    cJSON_AddBoolToObject(o, "default_allow", p.default_allow);
    cJSON *rules = cJSON_AddArrayToObject(o, "rules"),
          *forwards = cJSON_AddArrayToObject(o, "forwards");
    for (size_t i = 0; i < p.rule_count; i++) {
        ph_named_rule *n = &p.rules[i];
        ph_rule *v = &n->match;
        cJSON *x = cJSON_CreateObject();
        cJSON_AddItemToArray(rules, x);
        cJSON_AddStringToObject(x, "name", n->name);
        cJSON_AddBoolToObject(x, "enabled", n->enabled);
        cJSON_AddBoolToObject(x, "allow", v->allow);
        cJSON_AddStringToObject(x, "ingress", v->ingress == PH_AP ? "ap" : "usb");
        cJSON_AddNumberToObject(x, "protocol", v->protocol);
        add_cidr(x, "source", v->src, v->src_mask);
        add_cidr(x, "destination", v->dst, v->dst_mask);
        cJSON_AddNumberToObject(x, "port_first", v->port_first);
        cJSON_AddNumberToObject(x, "port_last", v->port_last);
    }
    for (size_t i = 0; i < p.forward_count; i++) {
        ph_port_forward *v = &p.forwards[i];
        cJSON *x = cJSON_CreateObject();
        cJSON_AddItemToArray(forwards, x);
        cJSON_AddStringToObject(x, "name", v->name);
        cJSON_AddBoolToObject(x, "enabled", v->enabled);
        cJSON_AddBoolToObject(x, "vpn", v->vpn);
        cJSON_AddBoolToObject(x, "active", active[i]);
        cJSON_AddNumberToObject(x, "protocol", v->protocol);
        cJSON_AddNumberToObject(x, "external_port", v->external_port);
        cJSON_AddNumberToObject(x, "internal_port", v->internal_port);
        add_cidr(x, "target", v->target, UINT32_MAX);
        add_cidr(x, "source", v->source, v->source_mask);
    }
    return json_reply(r, o);
}
static esp_err_t policy_post(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    cJSON *o = request_json(r, 12000), *rules = cJSON_GetObjectItemCaseSensitive(o, "rules"),
          *forwards = cJSON_GetObjectItemCaseSensitive(o, "forwards");
    ph_policy p = {.schema = 1};
    unsigned v = 0, revision = 0;
    bool valid = cJSON_IsObject(o) && json_int(o, "revision", UINT32_MAX, &revision) &&
                 json_bool(o, "default_allow", &p.default_allow) && cJSON_IsArray(rules) &&
                 cJSON_IsArray(forwards) && cJSON_GetArraySize(rules) <= PH_POLICY_RULES &&
                 cJSON_GetArraySize(forwards) <= PH_PORT_FORWARDS;
    cJSON *x;
    if (valid)
        cJSON_ArrayForEach(x, rules) {
            ph_named_rule *n = &p.rules[p.rule_count++];
            ph_rule *m = &n->match;
            const char *name = json_string(x, "name"), *in = json_string(x, "ingress");
            valid = name && strlen(name) < sizeof n->name && in &&
                    (!strcmp(in, "ap") || !strcmp(in, "usb"));
            if (!valid)
                break;
            strcpy(n->name, name);
            m->ingress = !strcmp(in, "ap") ? PH_AP : PH_USB;
            m->direction = PH_FORWARD;
            valid = json_bool(x, "enabled", &n->enabled) && json_bool(x, "allow", &m->allow) &&
                    get_cidr(x, "source", &m->src, &m->src_mask) &&
                    get_cidr(x, "destination", &m->dst, &m->dst_mask) &&
                    json_int(x, "protocol", 255, &v);
            m->protocol = v;
            valid = valid && json_int(x, "port_first", 65535, &v);
            m->port_first = v;
            valid = valid && json_int(x, "port_last", 65535, &v);
            m->port_last = v;
            if (!valid)
                break;
        }
    if (valid)
        cJSON_ArrayForEach(x, forwards) {
            ph_port_forward *f = &p.forwards[p.forward_count++];
            const char *name = json_string(x, "name");
            uint32_t mask;
            valid = name && strlen(name) < sizeof f->name;
            if (!valid)
                break;
            strcpy(f->name, name);
            valid = json_bool(x, "enabled", &f->enabled) && json_bool(x, "vpn", &f->vpn) &&
                    get_cidr(x, "source", &f->source, &f->source_mask) &&
                    get_cidr(x, "target", &f->target, &mask) && mask == UINT32_MAX &&
                    json_int(x, "protocol", 255, &v);
            f->protocol = v;
            valid = valid && json_int(x, "external_port", 65535, &v);
            f->external_port = v;
            valid = valid && json_int(x, "internal_port", 65535, &v);
            f->internal_port = v;
            if (!valid)
                break;
        }
    cJSON_Delete(o);
    if (!valid || !ph_policy_valid(&p))
        return reply(r, "400 Bad Request", "{\"error\":\"invalid_policy_or_reserved_port\"}");
    esp_err_t e = ph_gateway_policy_set(&p, revision);
    if (e == ESP_ERR_INVALID_STATE)
        return reply(r, "409 Conflict", "{\"error\":\"revision_conflict_reload\"}");
    if (e != ESP_OK)
        return reply(r, "500 Internal Server Error", "{\"error\":\"storage_failed\"}");
    return policy_get(r);
}
static esp_err_t vpn_get(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    return json_reply(r, ph_vpn_manager_status());
}
static esp_err_t vpn_command(httpd_req_t *r) {
    if (!auth(r))
        return reply(r, "401 Unauthorized", "{\"error\":\"authentication_required\"}");
    cJSON *o = request_json(r, 5000);
    esp_err_t e = ph_vpn_manager_command(o);
    cJSON *t = cJSON_GetObjectItemCaseSensitive(o, "token"),
          *p = cJSON_GetObjectItemCaseSensitive(o, "profile");
    if (cJSON_IsString(t))
        memset(t->valuestring, 0, strlen(t->valuestring));
    if (cJSON_IsString(p))
        memset(p->valuestring, 0, strlen(p->valuestring));
    cJSON_Delete(o);
    return reply(r,
                 e == ESP_OK                  ? "202 Accepted"
                 : e == ESP_ERR_INVALID_STATE ? "409 Conflict"
                                              : "400 Bad Request",
                 e == ESP_OK                  ? "{\"accepted\":true}"
                 : e == ESP_ERR_INVALID_STATE ? "{\"error\":\"command_in_progress\"}"
                                              : "{\"error\":\"invalid_vpn_configuration\"}");
}
static esp_err_t asset(httpd_req_t *r) {
    extern const unsigned char css_start[] asm("_binary_app_css_start"),
        css_end[] asm("_binary_app_css_end");
    extern const unsigned char js_start[] asm("_binary_app_js_start"),
        js_end[] asm("_binary_app_js_end");
    extern const unsigned char countries_start[] asm("_binary_countries_json_start"),
        countries_end[] asm("_binary_countries_json_end");
    const unsigned char *start, *end;
    const char *type;
    if (!strcmp(r->uri, "/app.css")) {
        start = css_start;
        end = css_end;
        type = "text/css";
    } else if (!strcmp(r->uri, "/app.js")) {
        start = js_start;
        end = js_end;
        type = "application/javascript";
    } else {
        start = countries_start;
        end = countries_end;
        type = "application/json";
    }
    httpd_resp_set_type(r, type);
    httpd_resp_set_hdr(r, "Cache-Control", "no-cache");
    httpd_resp_set_hdr(r, "X-Content-Type-Options", "nosniff");
    return httpd_resp_send(r, (const char *)start, end - start);
}
