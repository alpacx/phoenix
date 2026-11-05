#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "gateway.h"
#include "vpn.h"
#include "lwip/ip.h"
#include "lwip/etharp.h"
#include "esp_netif_net_stack.h"
#include "esp_mac.h"
#include "esp_log.h"
#include "tinyusb.h"
#include "tinyusb_net.h"
#include "tinyusb_default_config.h"
#include "lwip/tcpip.h"
#include "lwip/pbuf.h"
#include "lwip/netif.h"
#include "lwip/lwip_napt.h"
#include "dhcpserver/dhcpserver.h"
#include "lwip/ip4_addr.h"
#include "sdkconfig.h"
#ifndef CONFIG_PHOENIX_USB_LAB
#define CONFIG_PHOENIX_USB_LAB 0
#endif
esp_netif_t *ph_usb,*ph_eth;
static ph_firewall fw;
static uint8_t scratch[1514]; /* only accessed under lwIP core lock */
void ph_gateway_snapshot(ph_firewall *out){LOCK_TCPIP_CORE();fw.tunnel_ready=ph_vpn_up();*out=fw;UNLOCK_TCPIP_CORE();}
static void flush_nat(void){if(ph_eth)etharp_cleanup_netif(esp_netif_get_netif_impl(ph_eth));if(ph_usb){struct netif *n=esp_netif_get_netif_impl(ph_usb);ip_napt_enable_no(n->num,0);ip_napt_enable_no(n->num,1);}}
void ph_gateway_direct(bool enabled){LOCK_TCPIP_CORE();fw.direct_enabled=false;ph_vpn_stop();flush_nat();fw.direct_enabled=enabled;UNLOCK_TCPIP_CORE();}
void ph_gateway_uplink(bool ready){LOCK_TCPIP_CORE();fw.uplink_ready=ready;if(!ready){ph_vpn_stop();flush_nat();}UNLOCK_TCPIP_CORE();}
/* Runs in tcpip thread before NAT/local delivery; an unrecognized interface fails closed. */
int ph_ip4_input(struct pbuf *p,struct netif *n){
 ph_packet pkt;bool ok=false;
 if(p->tot_len>sizeof scratch)goto drop;
 pbuf_copy_partial(p,scratch,p->tot_len,0);
 if(!ph_parse_ipv4(scratch,p->tot_len,&pkt)){fw.malformed++;goto drop;}
 fw.tunnel_ready=ph_vpn_up();
 if(ph_usb&&n==esp_netif_get_netif_impl(ph_usb)){
  bool dhcp=pkt.protocol==17&&pkt.sport==68&&pkt.dport==67&&(pkt.dst==0xffffffff||pkt.dst==0xc0a80701);
  if(dhcp&&(pkt.src==0||(pkt.src&0xffffff00)==0xc0a80700))return 0;
  if((pkt.src&0xffffff00)!=0xc0a80700||pkt.src==0xc0a80701||pkt.src==0xc0a80700||pkt.src==0xc0a807ff)goto drop;
  if(pkt.dst==0xc0a80701)ok=ph_allow(&fw,scratch,p->tot_len,PH_USB,PH_USB,PH_LOCAL);
  else ok=ph_allow(&fw,scratch,p->tot_len,PH_USB,fw.direct_enabled?PH_ETH:PH_WG,PH_FORWARD);
 }else if(ph_eth&&n==esp_netif_get_netif_impl(ph_eth)){
  bool dhcp=pkt.protocol==17&&pkt.sport==67&&pkt.dport==68;
  if(!dhcp&&pkt.dst!=lwip_ntohl(netif_ip4_addr(n)->addr))goto drop;
  if(pkt.protocol==17&&ph_vpn_outer(pkt.src,pkt.sport,pkt.dport))return 0;
  /* No listening services on uplink except DHCP client. Return traffic is checked by NAPT. */
  ok=(pkt.protocol==17&&pkt.sport==67&&pkt.dport==68)||
     (fw.direct_enabled&&fw.uplink_ready&&(((pkt.protocol==6||pkt.protocol==17)&&pkt.dport>=1024)||(pkt.protocol==1&&scratch[20]==0)));
 }else if(n==ph_wg){
  ok=!fw.direct_enabled&&fw.uplink_ready&&fw.tunnel_ready&&pkt.dst==lwip_ntohl(netif_ip4_addr(n)->addr);
 }
 if(ok){
  if(!fw.direct_enabled&&ph_wg&&pkt.protocol==6){if(!ph_tcp_clamp_mss(scratch,p->tot_len,ph_wg->mtu))goto drop;if(pbuf_take(p,scratch,p->tot_len)!=ERR_OK)goto drop;}
  return 0;
 }
 drop:fw.blocked++;pbuf_free(p);return 1;
}
static netif_linkoutput_fn eth_linkoutput;
static err_t guarded_eth_output(struct netif *n,struct pbuf *p){
 if(!fw.direct_enabled){
  uint8_t b[1514];if(p->tot_len>sizeof b||p->tot_len<14)return ERR_IF;
  pbuf_copy_partial(p,b,p->tot_len,0);
  unsigned type=((unsigned)b[12]<<8)|b[13];
  if(type==0x800){ph_packet pkt;if(!ph_parse_ipv4(b+14,p->tot_len-14,&pkt))return ERR_IF;
   bool dhcp=pkt.protocol==17&&pkt.sport==68&&pkt.dport==67;
   bool encrypted=pkt.protocol==17&&ph_vpn_outer_tx(pkt.dst,pkt.sport,pkt.dport);
   if(!dhcp&&!encrypted){fw.blocked++;return ERR_IF;}
  }else if(type!=0x806)return ERR_IF;
 }
 return eth_linkoutput(n,p);
}
struct netif *ph_route(const ip4_addr_t *src,const ip4_addr_t *dst){
 if(ph_usb&&(lwip_ntohl(dst->addr)&0xffffff00)==0xc0a80700)return esp_netif_get_netif_impl(ph_usb);
 if(src&&(lwip_ntohl(src->addr)&0xffffff00)==0xc0a80700){
  if(!fw.direct_enabled&&ph_wg)return ph_wg;
  return ph_eth?esp_netif_get_netif_impl(ph_eth):NULL;
 }
 return NULL;
}
int ph_canforward(struct pbuf *p,unsigned long address){
 struct netif *in=ip_current_input_netif();
 if(!fw.uplink_ready)return 0;
 if(ph_usb&&in==esp_netif_get_netif_impl(ph_usb)){
  if(!fw.direct_enabled&&!ph_vpn_up())return 0;
 }else if(in==ph_wg){if(fw.direct_enabled||!ph_vpn_up())return 0;}
 else if(ph_eth&&in==esp_netif_get_netif_impl(ph_eth)){if(!fw.direct_enabled)return 0;}
 else return 0;
 return -1; /* preserve lwIP broadcast/multicast/loopback checks */
}
void ph_gateway_guard_eth(void){LOCK_TCPIP_CORE();struct netif *n=esp_netif_get_netif_impl(ph_eth);eth_linkoutput=n->linkoutput;n->linkoutput=guarded_eth_output;UNLOCK_TCPIP_CORE();}
static void free_rx(void *h,void *p){free(p);}
static void free_tx(void *p,void *ctx){free(p);}
static esp_err_t usb_tx(void *h,void *buf,size_t len){
 if(!tud_ready()||tud_suspended()||len>1514)return ESP_ERR_INVALID_STATE;
 void *copy=malloc(len);if(!copy)return ESP_ERR_NO_MEM;memcpy(copy,buf,len);
 esp_err_t e=tinyusb_net_send_sync(copy,len,copy,pdMS_TO_TICKS(10));if(e!=ESP_OK)free(copy);return e;
}
static esp_err_t usb_rx(void *buf,uint16_t len,void *ctx){
 const uint8_t *b=buf;
 if(len<14||len>1514)return ESP_OK;
 /* Only IPv4 and ARP. No VLAN bypass or IPv6 on the protected link. */
 unsigned type=((unsigned)b[12]<<8)|b[13];if(type!=0x800&&type!=0x806)return ESP_OK;
 if(type==0x806&&(len<42||b[14]!=0||b[15]!=1||b[16]!=8||b[17]!=0||b[18]!=6||b[19]!=4))return ESP_OK;
 void *copy=malloc(len);if(!copy)return ESP_ERR_NO_MEM;memcpy(copy,buf,len);
 return esp_netif_receive(ph_usb,copy,len,NULL); /* stack owns/free callback */
}
static void usb_event(tinyusb_event_t *e,void *arg){
 if(e->id==TINYUSB_EVENT_ATTACHED)esp_netif_action_connected(ph_usb,NULL,0,NULL);
 else esp_netif_action_disconnected(ph_usb,NULL,0,NULL);
}
/* NCM only. Prototype VID/PID from Espressif defaults; allocate a product identity before shipping. */
static const uint8_t fs_desc[]={
 TUD_CONFIG_DESCRIPTOR(1,2,0,TUD_CONFIG_DESC_LEN+TUD_CDC_NCM_DESC_LEN,TUSB_DESC_CONFIG_ATT_SELF_POWERED,0),
 TUD_CDC_NCM_DESCRIPTOR(0,4,5,0x81,64,2,0x82,64,1514)
};
static const uint8_t hs_desc[]={
 TUD_CONFIG_DESCRIPTOR(1,2,0,TUD_CONFIG_DESC_LEN+TUD_CDC_NCM_DESC_LEN,TUSB_DESC_CONFIG_ATT_SELF_POWERED,0),
 TUD_CDC_NCM_DESCRIPTOR(0,4,5,0x81,64,2,0x82,512,1514)
};
static char usb_serial[13];
static const char *usb_strings[]={"\x09\x04","Phoenix Lab","Phoenix NCM",usb_serial,"USB network","",NULL};
void ph_gateway_start(void){
 fw.rules[0]=(ph_rule){.ingress=PH_USB,.direction=PH_LOCAL,.protocol=6,.port_first=80,.port_last=80,.allow=true};
 fw.rules[1]=(ph_rule){.ingress=PH_USB,.direction=PH_FORWARD,.allow=true};fw.rule_count=2;
 if(!CONFIG_PHOENIX_USB_LAB){ESP_LOGW("gateway","USB held off: electrical fixture not approved");return;}
 if(CONFIG_PHOENIX_VBUS_GPIO!=5){ESP_LOGE("gateway","USB requires verified host VBUS sensing on reserved P1 GPIO5");return;}
 esp_netif_ip_info_t ip={0};IP4_ADDR(&ip.ip,192,168,7,1);IP4_ADDR(&ip.gw,192,168,7,1);IP4_ADDR(&ip.netmask,255,255,255,0);
 esp_netif_inherent_config_t base=ESP_NETIF_INHERENT_DEFAULT_ETH();
 base.flags=ESP_NETIF_DHCP_SERVER|ESP_NETIF_FLAG_AUTOUP;base.ip_info=&ip;base.if_key="USB";base.if_desc="usb";base.route_prio=0;base.get_ip_event=0;base.lost_ip_event=0;
 esp_netif_driver_ifconfig_t driver={.transmit=usb_tx,.driver_free_rx_buffer=free_rx};
 esp_netif_config_t c={.base=&base,.driver=&driver,.stack=ESP_NETIF_NETSTACK_DEFAULT_ETH};
 ph_usb=esp_netif_new(&c);ESP_ERROR_CHECK(ph_usb?ESP_OK:ESP_ERR_NO_MEM);
 uint8_t mac[6];ESP_ERROR_CHECK(esp_read_mac(mac,ESP_MAC_ETH));mac[0]|=2;mac[5]^=0x80;ESP_ERROR_CHECK(esp_netif_set_mac(ph_usb,mac));
 esp_netif_dns_info_t dns={.ip.type=ESP_IPADDR_TYPE_V4};IP4_ADDR(&dns.ip.u_addr.ip4,1,1,1,1);
 ESP_ERROR_CHECK(esp_netif_set_dns_info(ph_usb,ESP_NETIF_DNS_MAIN,&dns));
 dhcps_offer_t offer=OFFER_DNS;ESP_ERROR_CHECK(esp_netif_dhcps_option(ph_usb,ESP_NETIF_OP_SET,ESP_NETIF_DOMAIN_NAME_SERVER,&offer,sizeof offer));
 esp_netif_action_start(ph_usb,NULL,0,NULL);
 ESP_ERROR_CHECK(esp_netif_napt_enable(ph_usb));
 tinyusb_config_t tc=TINYUSB_DEFAULT_CONFIG(usb_event,NULL);tc.phy.self_powered=true;tc.phy.vbus_monitor_io=CONFIG_PHOENIX_VBUS_GPIO;
 snprintf(usb_serial,sizeof usb_serial,"%02X%02X%02X%02X%02X%02X",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
 tc.descriptor.full_speed_config=fs_desc;tc.descriptor.high_speed_config=hs_desc;tc.descriptor.string=usb_strings;tc.descriptor.string_count=6;
 ESP_ERROR_CHECK(tinyusb_driver_install(&tc));tinyusb_net_config_t nc={.on_recv_callback=usb_rx,.free_tx_buffer=free_tx};memcpy(nc.mac_addr,mac,6);ESP_ERROR_CHECK(tinyusb_net_init(&nc));
}
