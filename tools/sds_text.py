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


FURNITURE = re.compile(r'(?i)\bpage\b|\brevision\b|date of issue|\bversion\b|safety data sheet|according to|conforms to|printed|'
                       r'manufactured in|supersedes|\bsds\b|\bref\b|^\s*#\s*(?:/|of)\s*#\s*$|\(revision date\)')


def strip_page_furniture(text):
    """Remove page headers/footers that repeat on 3+ pages (page numbers normalised), keeping the first occurrence.
    Only lines that look like headers/footers (page numbers, revision/version/issue dates, 'according to ...') go."""
    lines = text.split('\n')
    key = lambda ln: re.sub(r'\d+', '#', ' '.join(ln.split()).lower())
    counts = {}
    for ln in lines:
        k = key(ln)
        if len(k) >= 3:
            counts[k] = counts.get(k, 0) + 1
    seen, out = set(), []
    for ln in lines:
        k = key(ln)
        if counts.get(k, 0) >= 3 and FURNITURE.search(k):
            if k in seen:
                continue
            seen.add(k)
        out.append(ln)
    return '\n'.join(out)


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
        # drop repeats of the section heading (page-continuation headers) inside the body
        first, rest = body.split('\n', 1) if '\n' in body else (body, '')
        hk = ' '.join(head.split()).lower()
        rest = '\n'.join(ln for ln in rest.split('\n') if ' '.join(ln.split()).lower() != hk)
        body = first + '\n' + rest
        subs = {}
        sub_iter = list(re.finditer(rf'(?m)^[ \t\f]*({n})\.(\d{{1,2}})\.?(?:\d\.?)?[ \t]+([^\n]*)$', body))
        for j, sm in enumerate(sub_iter):
            send = sub_iter[j + 1].start() if j + 1 < len(sub_iter) else len(body)
            key = f'{n}.{int(sm.group(2))}'
            subs.setdefault(key, body[sm.start():send].strip())
        sections[n] = {'heading': head, 'text': body.strip(), 'subsections': subs}
    return sections


SUB_TITLES = {  # Annex II subsection titles and common variants (used to separate a heading from text on the same line)
    '4.1': r'description of (?:necessary )?first[- ]aid measures|first aid measures', '4.2': r'most important symptoms[^:\n]*', '4.3': r'indication of [^:\n]*',
    '5.1': r'(?:fire )?extinguishing media', '5.2': r'special hazards? arising from the (?:substance|chemical|mixture)[^:\n]*|specific hazards[^:\n]*',
    '5.3': r'advice for fire-?fighters|fire[- ]?fighting instructions|special protective equipment[^:\n]*',
    '6.1': r'personal precautions[^:\n]*', '6.2': r'environmental precautions', '6.3': r'methods (?:and material )?for (?:containment and )?clean(?:ing)? ?up[^:\n]*|methods for cleaning up',
    '6.4': r'reference to other sections', '7.1': r'precautions for safe handling|handling', '7.2': r'conditions for safe storage[^:\n]*|storage',
    '7.3': r'specific end use\(?s?\)?', '8.1': r'control parameters|exposure guidelines', '8.2': r'exposure controls|engineering controls',
    '10.1': r'reactivity', '10.2': r'(?:chemical )?stability', '10.3': r'possibility of hazardous reactions|materials to avoid',
    '10.4': r'conditions to avoid|hazardous decomposition products?', '10.5': r'incompatib\w* materials', '10.6': r'hazardous decomposition products?',
}


def sub_body(raw, key):
    """Text of a subsection without its number and title, keeping any text printed on the heading line
    (two-column layouts put the heading and the content on one line)."""
    if not raw:
        return ''
    first, rest = (raw.split('\n', 1) + [''])[:2]
    line = re.sub(r'^\s*' + re.escape(key) + r'\.?\s*', '', first)
    m = re.match(r'(?i)\s*(?:' + SUB_TITLES.get(key, r'(?!x)x') + r')\s*[:.\-–]?\s*', line)
    if m:
        line = line[m.end():]
    elif re.match(r'[^.:]{2,70}?\s*:\s', line):
        line = re.sub(r'^[^.:]{2,70}?\s*:\s*', '', line, count=1)
    elif re.search(r'\S\s{2,}\S', line) and not re.search(r'[.;]', re.split(r'\s{2,}', line.strip())[0]):
        line = re.split(r'\s{2,}', line.strip(), maxsplit=1)[1]
    elif not re.search(r'[.;]', line) and len(line.strip()) <= 70:
        line = ''
    return ' '.join((line + '\n' + rest).split())


def transport_class(sec14_text, subsections=None):
    """First transport hazard class in Section 14 (e.g. '3', '2.1'), or None. Subsection numbers (14.4),
    UN numbers, packing groups and classification codes are never read as a class."""
    t = (subsections or {}).get('14.3') or ''
    if not t:
        m = re.search(r'(?is)(?:transport )?hazard class(?:\(es\)|es)?|un classification|adr/rid class|\bclass\b', sec14_text or '')
        t = (sec14_text or '')[max(0, m.start() - 60):m.end() + 120] if m else ''
    t = re.sub(r'\b14\.\d+\.?', ' ', t)
    t = re.sub(r'\bUN\s?\d{4}\b|\b\d{4}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b', ' ', t)
    m = re.search(r'(?<![\w.\-])([1-9](?:\.[1-6])?)[A-S]?(?![\w.%]|\.\d)', t)   # 1.1D: compatibility group letter
    return m.group(1) if m else None


def cas_ok(cas):
    digits = cas.replace('-', '')
    body, check = digits[:-1], int(digits[-1])
    return sum((i + 1) * int(d) for i, d in enumerate(reversed(body))) % 10 == check


UFI = re.compile(r'(?i)\bUFI\b\s*[:#]?\s*[A-Z0-9]{4}(?:\s*-\s*[A-Z0-9]{4}){3}|\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b')


def codes(text):
    text = UFI.sub(' ', text)   # UFI codes can contain H/P-like fragments (e.g. 3VD1-H039-E00E-U8SQ)
    return {
        'H': sorted(set(re.findall(r'(?<![A-Z0-9-])H[234]\d{2}(?:[A-Za-z]{1,2})?(?![0-9])', text))),
        'EUH': sorted(set(re.sub(r'\s', '', c) for c in re.findall(r'EUH\s?\d{3}A?', text))),
        'P': sorted(set(re.sub(r'\s', '', c) for c in re.findall(r'(?<![A-Z0-9])P\d{3}(?:\s*\+\s*P\d{3})*(?![0-9])', text))),
        'CAS': sorted(set(c for c in re.findall(r'(?<![\d-])\d{2,7}-\d{2}-\d(?![\d-])', text) if cas_ok(c))),
        'UN': sorted(set(re.findall(r'\bUN\s?(\d{4})\b', text))),
    }


if __name__ == '__main__':
    src, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    text = strip_page_furniture(to_text(src, out_dir))
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
