#include "wg_profile.h"
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
static char *trim(char *s){while(*s==' '||*s=='\t')s++;size_t n=strlen(s);while(n&&(s[n-1]==' '||s[n-1]=='\t'||s[n-1]=='\r'))s[--n]=0;return s;}
static bool number(const char *s,unsigned min,unsigned max,unsigned *out){if(!*s)return false;unsigned v=0;for(;*s;s++){if(*s<'0'||*s>'9'||v>max/10)return false;v=v*10+(*s-'0');if(v>max)return false;}if(v<min)return false;*out=v;return true;}
static bool ip(const char *s){unsigned parts=0;while(*s){char part[4];size_t n=0;while(*s&&*s!='.'){if(n==3)return false;part[n++]=*s++;}part[n]=0;unsigned v;if(!number(part,0,255,&v)||(n>1&&part[0]=='0'))return false;parts++;if(*s=='.'){s++;if(!*s)return false;}}return parts==4;}
static bool key(const char *s){if(strlen(s)!=44||s[43]!='=')return false;for(size_t i=0;i<43;i++)if(!isalnum((unsigned char)s[i])&&s[i]!='+'&&s[i]!='/')return false;const char *b="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";const char *p=strchr(b,s[42]);return p&&((p-b)%4)==0;}
static bool copy(char *dst,size_t cap,const char *v){size_t n=strlen(v);if(n>=cap)return false;memcpy(dst,v,n+1);return true;}
bool ph_wg_parse(const char *text,size_t len,ph_wg_profile *out){
 ph_wg_profile p={.mtu=1380};char line[256];unsigned section=0,seen=0;bool iface=false,peer=false;
 if(!text||!out||len==0||len>4096)return false;
 for(size_t pos=0;pos<len;){size_t n=0;while(pos<len&&text[pos]!='\n'){unsigned char c=text[pos++];if(!c||n==sizeof(line)-1)return false;line[n++]=c;}if(pos<len)pos++;line[n]=0;
  char *comment=strchr(line,'#');if(comment)*comment=0;char *s=trim(line);if(!*s)continue;
  if(!strcmp(s,"[Interface]")){if(iface||peer)return false;iface=true;section=1;continue;}
  if(!strcmp(s,"[Peer]")){if(!iface||peer)return false;peer=true;section=2;continue;}
  char *eq=strchr(s,'=');if(!eq)return false;*eq=0;char *name=trim(s),*v=trim(eq+1);unsigned bit=0,val;
  if(section==1&&!strcmp(name,"PrivateKey")){bit=1;if(!key(v)||!copy(p.private_key,45,v))return false;}
  else if(section==1&&!strcmp(name,"Address")){bit=2;char *slash=strchr(v,'/');if(!slash)return false;*slash=0;if(!number(slash+1,1,32,&val)||!ip(v)||!copy(p.address,16,v))return false;}
  else if(section==1&&!strcmp(name,"DNS")){bit=4;if(!ip(v)||!copy(p.dns,16,v))return false;}
  else if(section==1&&!strcmp(name,"MTU")){bit=8;if(!number(v,1280,1420,&val))return false;p.mtu=val;}
  else if(section==2&&!strcmp(name,"PublicKey")){bit=16;if(!key(v)||!copy(p.public_key,45,v))return false;}
  else if(section==2&&!strcmp(name,"PresharedKey")){bit=32;if(!key(v)||!copy(p.psk,45,v))return false;}
  else if(section==2&&!strcmp(name,"Endpoint")){bit=64;char *colon=strchr(v,':');if(!colon)return false;*colon=0;if(!ip(v)||!copy(p.endpoint,16,v)||!number(colon+1,1,65535,&val))return false;p.port=val;}
  else if(section==2&&!strcmp(name,"AllowedIPs")){bit=128;if(strcmp(v,"0.0.0.0/0"))return false;}
  else if(section==2&&!strcmp(name,"PersistentKeepalive")){bit=256;if(!number(v,0,65535,&val))return false;p.keepalive=val;}
  else return false;
  if(seen&bit)return false;
  seen|=bit;
 }
 if((seen&(1|2|4|16|64|128))!=(1|2|4|16|64|128))return false;
 *out=p;return true;
}
