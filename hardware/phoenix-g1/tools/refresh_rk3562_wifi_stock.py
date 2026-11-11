#!/usr/bin/env python3
"""Read public JLCPCB pages for selected references (default U26 group); no order or reservation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

R = Path(__file__).resolve().parents[1]/'migration-rk3562'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refs', nargs='+', default=['U26', 'L2201', 'C2201', 'C2202', 'C2203', 'C2204', 'R2201', 'R2202', 'R2203'])
parser.add_argument('--output', type=Path, default=R/'sourcing/wifi-converter-stock-refresh.json')
args = parser.parse_args()
refs = set(args.refs)
selection = json.loads((R/'sourcing/selected-references.json').read_text())
codes = {code: sorted(refs & set(names.split())) for code, names in selection.items() if refs & set(names.split())}
assert set().union(*(set(names) for names in codes.values())) == refs
baseline = json.loads((R/'sourcing/selected-main-parts.json').read_text())
mpns = {a['jlc']: a['mpn'] for a in baseline['parts']}


def fetch(code):
    url = 'https://jlcpcb.com/partdetail/'+code
    raw = urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()
    chunks = []
    for script in re.findall(r'self\.__next_f\.push\((.*?)\)</script>', raw.decode()):
        try:
            value = json.loads(script)
            if len(value) > 1 and isinstance(value[1], str):
                chunks.append(value[1])
        except ValueError:
            continue
    objects = {}
    for line in ''.join(chunks).splitlines():
        key, _, value = line.partition(':')
        try:
            objects[key] = json.JSONDecoder().raw_decode(value)[0]
        except ValueError:
            continue
    matching = [a for a in objects.values() if isinstance(a, dict) and a.get('componentCode') == code and 'canPresaleNumber' in a]
    assert len(matching) == 1, f'Cannot unambiguously read current stock: {code}'
    info = matching[0]
    assert info['componentModelEn'] == mpns[code], f'MPN mismatch: {code}'
    def walk(value):
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)
    found = { (a['startNumber'], a['endNumber'], a['productPrice'])
              for a in walk(objects) if a.get('componentCode') == code
              and all(key in a for key in ['startNumber', 'endNumber', 'productPrice']) }
    assert found, f'Cannot resolve public price breaks: {code}'
    assert len({a[0] for a in found}) == len(found), f'Conflicting price breaks: {code}'
    prices = [{'min_qty': lo, 'max_qty': hi, 'unit_usd': price} for lo, hi, price in sorted(found)]
    one = next(a['unit_usd'] for a in prices if a['min_qty'] == 1)
    return {'jlc': code, 'refs': codes[code], 'mpn': info['componentModelEn'], 'source': url,
            'checked_utc': datetime.now(timezone.utc).isoformat(), 'page_sha256': hashlib.sha256(raw).hexdigest(),
            'available_order_qty': info['canPresaleNumber'], 'displayed_stock': info['overseasStockCount'],
            'pre_min_purchase_qty': info.get('preMinPurchaseNum'), 'unit_usd_1plus': one, 'price_breaks': prices,
            'no_buy_reason': info.get('noBuyReason')}


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        observations = list(pool.map(fetch, sorted(codes)))
    report = {
        'status': 'PUBLIC STOCK OBSERVATION; NOT RESERVED OR PCBA ORDER CONFIRMATION',
        'currency': 'USD', 'parts': observations,
        'local_group_qty': len(refs),
        'local_group_1plus_subtotal': round(sum(a['unit_usd_1plus']*len(a['refs']) for a in observations), 4),
        'all_observed_order_quantities_positive': all(a['available_order_qty'] > 0 for a in observations),
        'limitations': ['Observed public presale and displayed stock are separate fields, not guaranteed assembly availability.',
                       '1+ prices do not include minimum purchase quantities, assembly, attrition, PCB, freight or taxes.',
                       'Only the requested reference group was refreshed; other board part dates remain unchanged.'],
    }
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
