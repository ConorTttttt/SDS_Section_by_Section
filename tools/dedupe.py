"""Engine-wide duplicate suppression (approved rule, all sections).

A finding may carry `items`: a list of {'key': str, 'text': str}. Two findings that share a key report the
same gap. The finding with the higher severity keeps the item; on a tie, the more specific layer wins
(B, L > A > C > D > J). The kept finding records `also_covers` (e.g. "4-C1 (P338)"); the other loses
the item, and is dropped when no items remain. Findings without items are never suppressed.
"""
import re

SEV = {'fail': 0, 'warning': 1, 'info': 2, 'not checked': 3}
LAYER = {'B': 0, 'L': 0, 'A': 1, 'C': 2, 'D': 3, 'J': 4}


def _layer(check):
    m = re.match(r'\d+-([A-Z])', check)
    return LAYER.get(m.group(1), 5) if m else 5


def dedupe(findings):
    order = sorted(range(len(findings)), key=lambda i: (SEV.get(findings[i]['status'], 9), _layer(findings[i]['check']), i))
    owner = {}
    drop = set()
    for i in order:
        f = findings[i]
        items = f.get('items')
        if not items:
            continue
        keep = []
        for it in items:
            o = owner.get(it['key'])
            if o is None:
                owner[it['key']] = i
                keep.append(it)
            else:
                kept = findings[o]
                if kept['check'] == f['check']:
                    continue
                kept.setdefault('also_covers', [])
                label = f"{f['check']} ({it['key'].split(':', 1)[-1]})"
                if label not in kept['also_covers']:
                    kept['also_covers'].append(label)
        if not keep:
            drop.add(i)
        elif len(keep) < len(items):
            f['items'] = keep
            if all('status' in x for x in keep):
                f['status'] = min((x['status'] for x in keep), key=lambda st: SEV.get(st, 9))
            if f.get('prefix') is not None:
                f['expected'] = f['prefix'] + '; '.join(x['text'] for x in keep) + f.get('suffix', '')
    out = []
    for i, f in enumerate(findings):
        if i in drop:
            continue
        if f.get('also_covers'):
            f['expected'] = f['expected'] + ' [also covers ' + ', '.join(f['also_covers']) + ']'
        out.append(f)
    return out
