"""Compare individual KiCad violations, not only category totals."""
from collections import Counter


def signatures(report):
    return Counter(
        (v['type'], v['severity'], tuple(sorted(i['uuid'] for i in v['items'])))
        for v in report['violations']
    )


def introduced(baseline, candidate):
    return [
        {'type': kind, 'severity': severity, 'items': list(items), 'count': count}
        for (kind, severity, items), count in (signatures(candidate) - signatures(baseline)).items()
    ]
