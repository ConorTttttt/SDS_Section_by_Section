"""Extract an SDS (PDF, DOCX, DOC, ODT, RTF, TXT) to text, split it into Sections 1-16 and their subsections,
and pull out hazard/precautionary codes, CAS numbers, UN numbers and dates.

Usage: python3 -I sds_text.py INPUT OUT_DIR
Writes OUT_DIR/sds.txt and OUT_DIR/sds.json.
"""
import json
import os
import re
import shutil
import subprocess
import sys

TITLES = {
    1: r'identification', 2: r'hazards?\s*(?:\(s\))?\s*identification', 3: r'composition',
    4: r'first[\s-]*aid', 5: r'fire[\s-]*fighting', 6: r'accidental\s+release', 7: r'handling|storage',
    8: r'exposure|personal\s+protection', 9: r'physical', 10: r'stability|reactivity',
    11: r'toxicologic', 12: r'ecologic', 13: r'disposal', 14: r'transport', 15: r'regulatory', 16: r'other\s+information',
}


def to_text(src, work):
    ext = os.path.splitext(src)[1].lower()
    if ext == '.pdf':
        out = os.path.join(work, 'sds_layout.txt')
        subprocess.run(['pdftotext', '-layout', src, out], check=True)
        text = open(out, encoding='utf-8', errors='ignore').read()
        if len(text.strip()) < 500:
            raise SystemExit('PDF has almost no text layer: it is probably scanned and needs OCR first.')
        return text
    if ext in ('.doc', '.odt', '.rtf'):
        subprocess.run(['soffice', '--headless', '--convert-to', 'docx', '--outdir', work, src],
                       check=True, capture_output=True)
        src = os.path.join(work, os.path.splitext(os.path.basename(src))[0] + '.docx')
        ext = '.docx'
    if ext == '.docx':
        return subprocess.run(['pandoc', '-t', 'plain', '--wrap=none', src], check=True,
                              capture_output=True, text=True).stdout
    return open(src, encoding='utf-8', errors='ignore').read()


def find_sections(text):
    cands = []
    for m in re.finditer(r'(?im)^[ \t\f>*#|]*(?:section|sec\.?|abschnitt|rubrique)?[ \t]*(\d{1,2})[ \t]*[.:)\-–—]?[ \t]*(?:[.:\-–—][ \t]*)?([^\n]{3,120})$', text):
        n = int(m.group(1))
        if n in TITLES and re.search(TITLES[n], m.group(2), re.I) and not re.match(r'\s*\d', m.group(2)):
            cands.append((m.start(), n, m.group(0).strip()))
    chosen, last_pos, last_n = {}, -1, 0
    for pos, n, head in cands:
        if n == last_n + 1 and pos > last_pos:
            chosen[n] = (pos, head)
            last_pos, last_n = pos, n
    # fall back: first heading per number in document order
    if len(chosen) < 10:
        chosen = {}
        for pos, n, head in cands:
            chosen.setdefault(n, (pos, head))
    order = sorted(chosen.items(), key=lambda kv: kv[1][0])
    sections = {}
    for i, (n, (pos, head)) in enumerate(order):
        end = order[i + 1][1][0] if i + 1 < len(order) else len(text)
        body = text[pos:end]
        subs = {}
        sub_iter = list(re.finditer(rf'(?m)^[ \t\f]*({n})\.(\d{{1,2}})\.?(?:\d\.?)?[ \t]+([^\n]*)$', body))
        for j, sm in enumerate(sub_iter):
            send = sub_iter[j + 1].start() if j + 1 < len(sub_iter) else len(body)
            key = f'{n}.{int(sm.group(2))}'
            subs.setdefault(key, body[sm.start():send].strip())
        sections[n] = {'heading': head, 'text': body.strip(), 'subsections': subs}
    return sections


def cas_ok(cas):
    digits = cas.replace('-', '')
    body, check = digits[:-1], int(digits[-1])
    return sum((i + 1) * int(d) for i, d in enumerate(reversed(body))) % 10 == check


def codes(text):
    return {
        'H': sorted(set(re.findall(r'(?<![A-Z0-9])H\d{3}(?:[A-Za-z]{1,2})?(?![0-9])', text))),
        'EUH': sorted(set(re.sub(r'\s', '', c) for c in re.findall(r'EUH\s?\d{3}A?', text))),
        'P': sorted(set(re.sub(r'\s', '', c) for c in re.findall(r'(?<![A-Z0-9])P\d{3}(?:\s*\+\s*P\d{3})*(?![0-9])', text))),
        'CAS': sorted(set(c for c in re.findall(r'(?<![\d-])\d{2,7}-\d{2}-\d(?![\d-])', text) if cas_ok(c))),
        'UN': sorted(set(re.findall(r'\bUN\s?(\d{4})\b', text))),
    }


if __name__ == '__main__':
    src, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    text = to_text(src, out_dir)
    open(os.path.join(out_dir, 'sds.txt'), 'w', encoding='utf-8').write(text)
    secs = find_sections(text)
    result = {
        'source': os.path.basename(src), 'chars': len(text),
        'sections_found': sorted(secs), 'sections': secs,
        'codes_all': codes(text),
        'codes_by_section': {n: codes(s['text']) for n, s in secs.items()},
        'dates': sorted(set(re.findall(r'\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\b', text[:4000]))),
    }
    json.dump(result, open(os.path.join(out_dir, 'sds.json'), 'w'), indent=1, ensure_ascii=False)
    print('sections found:', result['sections_found'])
    for n in (2, 3, 5, 6, 7, 9, 10, 14):
        if n in secs:
            print(f'  S{n}: {secs[n]["heading"][:70]!r} subsections={sorted(secs[n]["subsections"])}')
    print('codes:', {k: v[:25] for k, v in result['codes_all'].items()})
