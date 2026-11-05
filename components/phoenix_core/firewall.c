#include "phoenix.h"
#include <string.h>
static uint16_t u16(const uint8_t *p){return ((uint16_t)p[0]<<8)|p[1];}
static uint32_t u32(const uint8_t *p){return ((uint32_t)u16(p)<<16)|u16(p+2);}
bool ph_parse_ipv4(const uint8_t *d,size_t n,ph_packet *p){
 if(!d||!p||n<20||d[0]!=0x45) return false; /* options rejected */
 size_t total=u16(d+2); if(total<20||total>n||(u16(d+6)&0xbfff)) return false; /* no fragments/reserved */
 uint32_t sum=0;for(size_t i=0;i<20;i+=2)sum+=u16(d+i);
 while(sum>>16)sum=(sum&65535)+(sum>>16);
 if(sum!=65535||d[8]==0)return false;
 memset(p,0,sizeof(*p));p->src=u32(d+12);p->dst=u32(d+16);p->protocol=d[9];
 size_t payload=total-20;
 if(p->protocol==6){if(payload<20||(d[32]>>4)<5||(size_t)(d[32]>>4)*4>payload)return false;p->tcp_flags=d[33];}
 else if(p->protocol==17){if(payload<8||u16(d+24)!=payload)return false;}
 else if(p->protocol==1){if(payload<8)return false;}
 else return false;
 if(p->protocol==6||p->protocol==17){p->sport=u16(d+20);p->dport=u16(d+22);}
 return true;
}
bool ph_allow(ph_firewall *f,const uint8_t *d,size_t n,ph_iface in,ph_iface out,ph_direction dir){
 ph_packet p;if(!ph_parse_ipv4(d,n,&p)){f->malformed++;f->blocked++;return false;}
 /* Mandatory gate precedes every configurable allow. Tunnel state alone never permits cleartext egress. */
 if(dir==PH_FORWARD){
  if(!f->uplink_ready)goto deny;
  if(!f->direct_enabled && (out!=PH_WG||!f->tunnel_ready))goto deny;
 }
 if(f->rule_count>PH_MAX_RULES)goto deny;
 for(size_t i=0;i<f->rule_count;i++){
  const ph_rule *r=&f->rules[i];
  if(r->ingress!=in||r->direction!=dir||(r->protocol&&r->protocol!=p.protocol))continue;
  if((p.src&r->src_mask)!=(r->src&r->src_mask)||(p.dst&r->dst_mask)!=(r->dst&r->dst_mask))continue;
  if(r->port_first||r->port_last){if(p.protocol!=6&&p.protocol!=17)continue;if(p.dport<r->port_first||p.dport>r->port_last)continue;}
  if(!r->allow)goto deny;
  f->allowed++;return true;
 }
 deny:f->blocked++;return false;
}
bool ph_tcp_clamp_mss(uint8_t *d,size_t n,uint16_t mtu){
 ph_packet p;if(mtu<576||!ph_parse_ipv4(d,n,&p))return false;
 if(p.protocol!=6||!(p.tcp_flags&2))return true;
 size_t end=20+(size_t)(d[32]>>4)*4;
 for(size_t i=40;i<end;){
  unsigned kind=d[i];if(kind==0)break;if(kind==1){i++;continue;}
  if(i+2>end||d[i+1]<2||i+d[i+1]>end)return false;
  if(kind==2){if(d[i+1]!=4)return false;uint16_t old=u16(d+i+2),value=mtu-40;
   if(old>value){unsigned sum=(unsigned)(~u16(d+36)&65535)+(~old&65535)+value;while(sum>>16)sum=(sum&65535)+(sum>>16);uint16_t c=(uint16_t)~sum;d[36]=c>>8;d[37]=c;d[i+2]=value>>8;d[i+3]=value;}
  }i+=d[i+1];
 }return true;
}
