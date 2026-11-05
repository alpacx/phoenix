#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "admin.h"
#include "gateway.h"
#include "vpn.h"
#include "lwip/tcpip.h"
#include <sys/time.h>
#include "esp_http_server.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "nvs.h"
#include "mbedtls/sha256.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
static uint8_t digest[32];static bool paired;static SemaphoreHandle_t mutex;
static const char page[]=
"<!doctype html><html lang=it><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Phoenix</title>"
"<style>body{font:17px system-ui;max-width:48rem;margin:5vh auto;padding:1rem;background:#102029;color:#e2f4ed}button,input{font:inherit;padding:.7rem;margin:.4rem 0;max-width:95%}button{cursor:pointer}pre{white-space:pre-wrap;background:#20343e;padding:1rem}label{display:block}</style>"
"<h1>Phoenix · laboratorio</h1><p>Il dispositivo controlla solo il traffico che lo attraversa. IPv6 bloccato. WireGuard sperimentale; Wi-Fi non disponibile.</p>"
"<label>Token amministrativo <input id=t type=password autocomplete=off size=50></label><button id=s>Leggi stato</button> <button id=b>Blocca inoltro</button> <button id=d>Abilita Internet diretto</button><pre id=o>Pairing tramite seriale nei primi 120 secondi dall’avvio.</pre>"
"<script>async function call(path,body){try{let r=await fetch('/api/v1/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+t.value,'Content-Type':'application/json'},body:body&&JSON.stringify(body)});o.textContent=JSON.stringify(await r.json(),null,2)}catch(e){o.textContent='Richiesta fallita'}}s.onclick=()=>call('status');b.onclick=()=>call('mode',{direct:false});d.onclick=()=>{if(confirm('Consenti traffico senza VPN? Le sessioni possono interrompersi.'))call('mode',{direct:true})}</script></html>";
static esp_err_t reply(httpd_req_t *r,const char *status,const char *body){httpd_resp_set_status(r,status);httpd_resp_set_type(r,"application/json");httpd_resp_set_hdr(r,"Cache-Control","no-store");return httpd_resp_sendstr(r,body);}
static bool auth(httpd_req_t *r){
 char token[72];if(httpd_req_get_hdr_value_len(r,"Authorization")!=71||httpd_req_get_hdr_value_str(r,"Authorization",token,sizeof token)!=ESP_OK||memcmp(token,"Bearer ",7))return false;
 uint8_t hash[32];mbedtls_sha256((uint8_t*)token+7,64,hash,0);memset(token,0,sizeof token);
 xSemaphoreTake(mutex,portMAX_DELAY);unsigned diff=paired?0:1;for(size_t i=0;i<32;i++)diff|=hash[i]^digest[i];xSemaphoreGive(mutex);memset(hash,0,sizeof hash);return diff==0;
}
static esp_err_t index_page(httpd_req_t *r){httpd_resp_set_type(r,"text/html");httpd_resp_set_hdr(r,"Cache-Control","no-store");httpd_resp_set_hdr(r,"X-Frame-Options","DENY");return httpd_resp_sendstr(r,page);}
static esp_err_t status(httpd_req_t *r){
 if(!auth(r))return reply(r,"401 Unauthorized","{\"error\":\"authentication_required\"}");
 ph_firewall f;ph_gateway_snapshot(&f);char out[500];snprintf(out,sizeof out,"{\"api_version\":1,\"ethernet_ready\":%s,\"usb_configured\":%s,\"direct\":%s,\"vpn_up\":%s,\"wifi\":\"unavailable\",\"allowed\":%llu,\"blocked\":%llu,\"malformed\":%llu,\"heap_free\":%lu,\"uptime_ms\":%lld}",f.uplink_ready?"true":"false",ph_usb?"true":"false",f.direct_enabled?"true":"false",f.tunnel_ready?"true":"false",f.allowed,f.blocked,f.malformed,(unsigned long)esp_get_free_heap_size(),esp_timer_get_time()/1000);
 return reply(r,"200 OK",out);
}
static esp_err_t mode(httpd_req_t *r){
 if(!auth(r))return reply(r,"401 Unauthorized","{\"error\":\"authentication_required\"}");
 char origin[64];size_t ol=httpd_req_get_hdr_value_len(r,"Origin");if(ol&&(ol>=sizeof origin||httpd_req_get_hdr_value_str(r,"Origin",origin,sizeof origin)!=ESP_OK||strcmp(origin,"http://192.168.7.1")))return reply(r,"403 Forbidden","{\"error\":\"origin\"}");
 if(r->content_len<2||r->content_len>64)return reply(r,"400 Bad Request","{\"error\":\"size\"}");
 char body[65];size_t have=0;while(have<r->content_len){int n=httpd_req_recv(r,body+have,r->content_len-have);if(n<=0)return ESP_FAIL;have+=n;}body[have]=0;
 const char *end=NULL;cJSON *obj=cJSON_ParseWithOpts(body,&end,true);cJSON *d=cJSON_GetObjectItemCaseSensitive(obj,"direct");
 if(!cJSON_IsObject(obj)||cJSON_GetArraySize(obj)!=1||!cJSON_IsBool(d)){cJSON_Delete(obj);return reply(r,"400 Bad Request","{\"error\":\"expected_direct_boolean\"}");}
 ph_gateway_direct(cJSON_IsTrue(d));cJSON_Delete(obj);return reply(r,"200 OK","{\"ok\":true}");
}
static esp_err_t vpn_import(httpd_req_t *r){
 if(!auth(r))return reply(r,"401 Unauthorized","{\"error\":\"authentication_required\"}");
 if(httpd_req_get_hdr_value_len(r,"Origin"))return reply(r,"403 Forbidden","{\"error\":\"use_local_client\"}");
 if(r->content_len<1||r->content_len>4096)return reply(r,"400 Bad Request","{\"error\":\"size\"}");
 char *body=calloc(1,r->content_len+1);if(!body)return ESP_ERR_NO_MEM;
 size_t have=0;while(have<r->content_len){int n=httpd_req_recv(r,body+have,r->content_len-have);if(n<=0){memset(body,0,r->content_len);free(body);return ESP_FAIL;}have+=n;}
 ph_wg_profile profile;bool valid=ph_wg_parse(body,have,&profile);memset(body,0,have);free(body);
 if(!valid)return reply(r,"400 Bad Request","{\"error\":\"unsupported_or_malformed_profile\"}");
 ph_gateway_direct(false);
 LOCK_TCPIP_CORE();bool started=ph_vpn_start(&profile);UNLOCK_TCPIP_CORE();
 if(started&&ph_usb){esp_netif_dns_info_t dns={0};dns.ip.type=ESP_IPADDR_TYPE_V4;esp_netif_str_to_ip4(profile.dns,&dns.ip.u_addr.ip4);esp_netif_set_dns_info(ph_usb,ESP_NETIF_DNS_MAIN,&dns);}
 memset(&profile,0,sizeof profile);
 return reply(r,started?"202 Accepted":"409 Conflict",started?"{\"state\":\"connecting\",\"renew_dhcp\":true}":"{\"error\":\"clock_uplink_or_vpn_init\",\"forwarding\":\"blocked\"}");
}
/* Provision over local UART only. No token is printed, echoed or accepted over the uplink. */
static void serial_pair(void *arg){
 char line[80];size_t n=0;bool overflow=false;
 while(esp_timer_get_time()<120000000){int ch=getchar();if(ch==EOF){vTaskDelay(pdMS_TO_TICKS(20));continue;}
  if(ch=='\n'||ch=='\r'){
   if(!overflow&&n==15&&!memcmp(line,"time ",5)){bool valid=true;for(size_t i=5;i<15;i++)if(line[i]<'0'||line[i]>'9')valid=false;if(valid){line[15]=0;long long epoch=atoll(line+5);if(epoch>=1700000000LL&&epoch<=4102444800LL){struct timeval tv={.tv_sec=epoch};settimeofday(&tv,NULL);puts("Clock set");}}}
   if(!overflow&&n==69&&!memcmp(line,"pair ",5)){
    bool valid=true;for(size_t i=5;i<69;i++)if(!((line[i]>='0'&&line[i]<='9')||(line[i]>='a'&&line[i]<='f')))valid=false;
    if(valid){uint8_t h[32];mbedtls_sha256((uint8_t*)line+5,64,h,0);nvs_handle_t nv;
     if(nvs_open("phoenix",NVS_READWRITE,&nv)==ESP_OK){
      esp_err_t e=nvs_set_blob(nv,"admin",h,32);if(e==ESP_OK)e=nvs_set_u32(nv,"version",1);if(e==ESP_OK)e=nvs_commit(nv);nvs_close(nv);
      if(e==ESP_OK){xSemaphoreTake(mutex,portMAX_DELAY);memcpy(digest,h,32);paired=true;xSemaphoreGive(mutex);puts("Pairing saved");}
     }memset(h,0,sizeof h);
    }
   }memset(line,0,sizeof line);n=0;overflow=false;
  }else if(n<sizeof line)n++,line[n-1]=(char)ch;else overflow=true;
 }memset(line,0,sizeof line);vTaskDelete(NULL);
}
void ph_admin_start(void){
 mutex=xSemaphoreCreateMutex();configASSERT(mutex);nvs_handle_t nv;
 if(nvs_open("phoenix",NVS_READONLY,&nv)==ESP_OK){uint32_t version=0;size_t len=32;if(nvs_get_u32(nv,"version",&version)==ESP_OK&&version==1&&nvs_get_blob(nv,"admin",digest,&len)==ESP_OK&&len==32)paired=true;nvs_close(nv);}
 configASSERT(xTaskCreate(serial_pair,"pair",4096,NULL,3,NULL)==pdPASS);
 if(!ph_usb)return;
 httpd_config_t c=HTTPD_DEFAULT_CONFIG();c.max_uri_handlers=5;c.stack_size=6144;c.recv_wait_timeout=3;c.send_wait_timeout=3;
 httpd_handle_t server;ESP_ERROR_CHECK(httpd_start(&server,&c));
 const httpd_uri_t routes[]={{.uri="/",.method=HTTP_GET,.handler=index_page},{.uri="/api/v1/status",.method=HTTP_GET,.handler=status},{.uri="/api/v1/mode",.method=HTTP_POST,.handler=mode},{.uri="/api/v1/vpn",.method=HTTP_POST,.handler=vpn_import}};
 for(size_t i=0;i<sizeof routes/sizeof routes[0];i++)ESP_ERROR_CHECK(httpd_register_uri_handler(server,&routes[i]));
}
