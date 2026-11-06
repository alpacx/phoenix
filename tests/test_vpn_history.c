/* Compile against flash/clock test doubles; exercises the production journal. */
#define time history_test_time
#include "../main/vpn_history.c"
#undef time
#include <assert.h>
static unsigned char flash[32*4096];
static time_t current_time=1800000000;
static const esp_partition_t test_partition={sizeof flash};
time_t history_test_time(time_t *p){if(p)*p=current_time;return current_time;}
const esp_partition_t *esp_partition_find_first(int a,int b,const char*c){(void)a;(void)b;(void)c;return &test_partition;}
int esp_partition_read(const esp_partition_t*p,size_t o,void*b,size_t n){(void)p;assert(o+n<=sizeof flash);memcpy(b,flash+o,n);return 0;}
int esp_partition_write(const esp_partition_t*p,size_t o,const void*b,size_t n){(void)p;assert(o+n<=sizeof flash);for(size_t i=0;i<n;i++){assert((flash[o+i]&((const uint8_t*)b)[i])==((const uint8_t*)b)[i]);flash[o+i]&=((const uint8_t*)b)[i];}return 0;}
int esp_partition_erase_range(const esp_partition_t*p,size_t o,size_t n){(void)p;assert(o%4096==0&&n==4096);memset(flash+o,255,n);return 0;}
uint32_t esp_crc32_le(uint32_t crc,const uint8_t*b,size_t n){crc=~crc;while(n--){crc^=*b++;for(int j=0;j<8;j++)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}return ~crc;}
static void reboot(void){memset(records,0,sizeof records);sequence=0;next_slot=0;ph_history_init();}
int main(void){
 memset(flash,255,sizeof flash);ph_history_init();
 for(int i=0;i<1000;i++){ph_history_add("IT","Italy #1",1);current_time+=30;}
 reboot();unsigned total=0;uint32_t before=0,last=UINT32_MAX;
 do{cJSON *o=ph_history_page(before);cJSON *a=cJSON_GetObjectItem(o,"entries");cJSON *v; cJSON_ArrayForEach(v,a){uint32_t id=cJSON_GetObjectItem(v,"id")->valueint;assert(id<last);last=id;total++;}before=cJSON_GetObjectItem(o,"next_before")->valueint;cJSON_Delete(o);}while(before);
 assert(total==959);
 for(int i=0;i<500;i++){ph_history_add("DE","Germany #1",2);current_time+=30;}
 reboot();assert(sequence==1500);
 /* A torn next write must not overwrite programmed flash. */
 flash[offset(next_slot)]=0;reboot();ph_history_add("FR","France #1",3);reboot();assert(sequence==1501);
 current_time+=28800;cJSON *o=ph_history_page(0);assert(cJSON_GetArraySize(cJSON_GetObjectItem(o,"entries"))==0);cJSON_Delete(o);
 puts("History: eight-hour expiry, pagination, ring wrap, reboot and torn-write recovery PASS");
}
