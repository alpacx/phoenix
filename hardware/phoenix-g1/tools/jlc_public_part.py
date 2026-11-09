#!/usr/bin/env python3
"""Read public JLCPCB product-page data. Does not access accounts or submit orders.
Retains raw inventory field names: presale and overseas counts are not interchangeable
with immediately available PCBA stock. No signed download URLs are saved in reports.
"""
import argparse,datetime,json,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def get(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read()
def fetch(url):
 html=get(url).decode();payload=''.join(json.loads(s)[1] for s in re.findall(r'self\.__next_f\.push\((\[1,.*?\])\)</script>',html))
 objects=[]
 for m in re.finditer('"componentInfo":',payload):
  try:o=json.JSONDecoder().raw_decode(payload[m.end():])[0]
  except (ValueError,IndexError):continue
  if isinstance(o,dict):objects.append(o)
 merged={}
 for o in objects:
  for k,v in o.items():
   if not isinstance(v,str) or not v.startswith('$'):merged[k]=v
 if 'componentCode' not in merged:raise RuntimeError('No public product record found')
 return merged
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--pdf');a=p.parse_args();o=fetch(a.url)
 wanted=['componentCode','componentModelEn','componentBrandEn','componentSpecificationEn','describe','canPresaleNumber','overseasStockCount','stockCount','initialPrice','prices','leastPatchNumber','preMinPurchaseNum','assemblyComponentFlag','componentLibraryType']
 record={k:o[k] for k in wanted if k in o};record.update({'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_url':a.url,'inventory_note':'Raw public site fields. Overseas/presale numbers are not independently verified immediate assembly stock.'})
 dest=ROOT/'sourcing/public';dest.mkdir(exist_ok=True);(dest/(o['componentCode']+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 if a.pdf:
  url=o.get('dataManualFileAccessIdUrl') or o.get('dataManualUrl')
  if not url:raise RuntimeError('No datasheet URL')
  d=get(url)
  if not d.startswith(b'%PDF'):
   urls=re.findall(rb'https://datasheet.lcsc.com/[^"<> ]+',d)
   if urls:d=get(urls[0].decode())
  if not d.startswith(b'%PDF'):raise RuntimeError('Datasheet response is not PDF')
  (ROOT/'reference'/a.pdf).write_bytes(d)
 print(json.dumps({k:record[k] for k in ['componentCode','componentModelEn','canPresaleNumber','overseasStockCount','stockCount','initialPrice'] if k in record}))
